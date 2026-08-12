from __future__ import annotations

import asyncio
import re
import struct
import time
import uuid
import zlib
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx

from app.agent.graph import build_agent_graph
from app.agent.state import AgentEvidence
from app.agent.tools import RetrievalTool
from app.evaluation.benchmark_datasets import (
    ChartQABenchmarkQuestion,
    HotpotBenchmarkQuestion,
    NanoSciFactBenchmark,
)
from app.evaluation.benchmark_store import (
    BenchmarkDocument,
    InMemoryBenchmarkStore,
    embed_documents,
)
from app.evaluation.dataset import EvaluationDataset
from app.evaluation.runner import EvaluationResult, EvaluationRunner
from app.infrastructure.chat_client import ChatCompletionResult, ChatMessage, ExternalModelError
from app.parsers.types import ParsedDocument


class EmbeddingsProtocol(Protocol):
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...


class ChatProtocol(Protocol):
    async def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletionResult: ...


class ParserProtocol(Protocol):
    async def parse_pdf(self, filename: str, content: bytes) -> ParsedDocument: ...


@dataclass(frozen=True, slots=True)
class AgenticModeMetrics:
    answer_exact_match: float
    answer_f1: float
    answer_containment_accuracy: float
    supporting_document_recall: float
    average_retrievals: float
    average_chat_calls: float


@dataclass(frozen=True, slots=True)
class AgenticBenchmarkResult:
    dataset_size: int
    baseline: AgenticModeMetrics
    enhanced: AgenticModeMetrics
    improvement: dict[str, float]
    questions: list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class ChartQAModeMetrics:
    answer_accuracy: float
    document_parse_success_rate: float
    asset_extraction_rate: float
    average_chat_latency_ms: float


@dataclass(frozen=True, slots=True)
class ChartQABenchmarkResult:
    dataset_size: int
    baseline: ChartQAModeMetrics
    enhanced: ChartQAModeMetrics
    improvement: dict[str, float]
    parse_success_rate: float
    average_parser_latency_ms: float
    questions: list[dict[str, object]]


class CountingChatClient:
    def __init__(self, client: ChatProtocol) -> None:
        self._client = client
        self.calls = 0

    async def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        self.calls += 1
        return await self._client.complete(messages)


class RetryingChatClient:
    def __init__(self, client: ChatProtocol, *, max_attempts: int = 4) -> None:
        self._client = client
        self._max_attempts = max(max_attempts, 1)

    async def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        for attempt in range(self._max_attempts):
            try:
                return await self._client.complete(messages)
            except ExternalModelError as exc:
                retryable = (
                    exc.status_code is None
                    or exc.status_code in {408, 429}
                    or (exc.status_code >= 500)
                )
                if not retryable or attempt + 1 >= self._max_attempts:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError("chat retry loop exhausted")


async def run_retrieval_benchmark(
    benchmark: NanoSciFactBenchmark,
    *,
    embeddings: EmbeddingsProtocol,
    reranker: Any,
    top_k: int = 5,
    embedding_batch_size: int = 32,
) -> EvaluationResult:
    documents = [
        BenchmarkDocument(
            document_id=document_id,
            filename=f"nanoscifact-{document_id}.txt",
            text=text,
        )
        for document_id, text in benchmark.corpus.items()
    ]
    indexed = await embed_documents(documents, embeddings, batch_size=embedding_batch_size)
    store = InMemoryBenchmarkStore()
    store.replace_documents(indexed)
    runner = EvaluationRunner(
        knowledge_base_id=uuid.uuid5(uuid.NAMESPACE_URL, "nanoscifact-evaluation"),
        store=store,
        embeddings=embeddings,
        reranker=reranker,
        limit=top_k,
    )
    return await runner.run(EvaluationDataset(questions=benchmark.questions))


async def run_agentic_benchmark(
    questions: Sequence[HotpotBenchmarkQuestion],
    *,
    embeddings: EmbeddingsProtocol,
    reranker: Any,
    chat_client: ChatProtocol,
    top_k: int = 3,
    max_retrievals: int = 3,
    embedding_batch_size: int = 32,
    max_concurrency: int = 4,
    progress_callback: Callable[[int, int], None] | None = None,
) -> AgenticBenchmarkResult:
    semaphore = asyncio.Semaphore(max(max_concurrency, 1))
    retrying_chat = RetryingChatClient(chat_client)
    completed = 0
    total = len(questions)

    async def evaluate(item: HotpotBenchmarkQuestion) -> dict[str, object]:
        nonlocal completed
        async with semaphore:
            store = InMemoryBenchmarkStore()
            retrieval_service = store.as_hybrid_service(
                embeddings=embeddings,
                reranker=reranker,
            )
            retrieval_tool = RetrievalTool(service=retrieval_service, limit=top_k)
            counting_chat = CountingChatClient(retrying_chat)
            graph = build_agent_graph(
                chat_client=counting_chat,
                retrieval_tool=retrieval_tool,
                max_retrievals=max_retrievals,
                force_retrieval=True,
            )
            documents = [
                BenchmarkDocument(
                    document_id=context.document_id,
                    filename=context.title,
                    text=context.text,
                    metadata={"title": context.title},
                )
                for context in item.context
            ]
            indexed = await embed_documents(
                documents,
                embeddings,
                batch_size=embedding_batch_size,
            )
            store.replace_documents(indexed)
            knowledge_base_id = uuid.uuid4()

            baseline_evidence = await retrieval_tool.run(
                knowledge_base_id=knowledge_base_id,
                query=item.question,
            )
            baseline_completion = await counting_chat.complete(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "Answer using only the provided evidence. Return only the shortest "
                            "answer span followed by source labels. For yes/no questions, return "
                            "only Yes or No followed by source labels. Do not explain."
                        ),
                    ),
                    ChatMessage(
                        role="user",
                        content=_rag_answer_prompt(item.question, baseline_evidence),
                    ),
                ]
            )
            baseline_answer = baseline_completion.content.strip()
            baseline_retrieved_titles = {
                str(evidence_item.metadata.get("title", evidence_item.filename))
                for evidence_item in baseline_evidence
            }

            counting_chat.calls = 0
            result = cast(
                Mapping[str, object],
                await cast(Any, graph).ainvoke(
                    {"query": item.question, "knowledge_base_id": str(knowledge_base_id)},
                    {"configurable": {"thread_id": f"benchmark-{item.id}"}},
                ),
            )
            answer = str(result.get("final_answer", ""))
            evidence = _evidence_list(result.get("evidence"))
            retrieved_titles = {
                str(evidence_item.metadata.get("title", evidence_item.filename))
                for evidence_item in evidence
            }
            completed += 1
            if progress_callback is not None:
                progress_callback(completed, total)
            return {
                "id": item.id,
                "expected_answer": item.answer,
                "baseline_answer_exact_match": _exact_match(baseline_answer, item.answer),
                "baseline_answer_f1": _token_f1(baseline_answer, item.answer),
                "baseline_answer_containment": _answer_contains(baseline_answer, item.answer),
                "baseline_supporting_document_recall": _set_recall(
                    item.supporting_titles,
                    baseline_retrieved_titles,
                ),
                "baseline_retrieval_count": 1,
                "baseline_chat_calls": 1,
                "baseline_answer": baseline_answer,
                "enhanced_answer_exact_match": _exact_match(answer, item.answer),
                "enhanced_answer_f1": _token_f1(answer, item.answer),
                "enhanced_answer_containment": _answer_contains(answer, item.answer),
                "enhanced_supporting_document_recall": _set_recall(
                    item.supporting_titles,
                    retrieved_titles,
                ),
                "enhanced_retrieval_count": _int_value(result.get("retrieval_count", 0)),
                "enhanced_chat_calls": counting_chat.calls,
                "enhanced_answer": answer,
            }

    raw_rows = await asyncio.gather(
        *(evaluate(item) for item in questions),
        return_exceptions=True,
    )
    rows: list[dict[str, object]] = []
    for item, raw_row in zip(questions, raw_rows, strict=True):
        if isinstance(raw_row, BaseException):
            rows.append(_failed_agentic_row(item, raw_row))
            completed += 1
            if progress_callback is not None:
                progress_callback(completed, total)
        else:
            rows.append(raw_row)

    baseline = AgenticModeMetrics(
        answer_exact_match=_average(row["baseline_answer_exact_match"] for row in rows),
        answer_f1=_average(row["baseline_answer_f1"] for row in rows),
        answer_containment_accuracy=_average(row["baseline_answer_containment"] for row in rows),
        supporting_document_recall=_average(
            row["baseline_supporting_document_recall"] for row in rows
        ),
        average_retrievals=_average(row["baseline_retrieval_count"] for row in rows),
        average_chat_calls=_average(row["baseline_chat_calls"] for row in rows),
    )
    enhanced = AgenticModeMetrics(
        answer_exact_match=_average(row["enhanced_answer_exact_match"] for row in rows),
        answer_f1=_average(row["enhanced_answer_f1"] for row in rows),
        answer_containment_accuracy=_average(row["enhanced_answer_containment"] for row in rows),
        supporting_document_recall=_average(
            row["enhanced_supporting_document_recall"] for row in rows
        ),
        average_retrievals=_average(row["enhanced_retrieval_count"] for row in rows),
        average_chat_calls=_average(row["enhanced_chat_calls"] for row in rows),
    )
    return AgenticBenchmarkResult(
        dataset_size=len(rows),
        baseline=baseline,
        enhanced=enhanced,
        improvement={
            "answer_exact_match": enhanced.answer_exact_match - baseline.answer_exact_match,
            "answer_f1": enhanced.answer_f1 - baseline.answer_f1,
            "answer_containment_accuracy": (
                enhanced.answer_containment_accuracy - baseline.answer_containment_accuracy
            ),
            "supporting_document_recall": (
                enhanced.supporting_document_recall - baseline.supporting_document_recall
            ),
        },
        questions=rows,
    )


def _failed_agentic_row(
    item: HotpotBenchmarkQuestion,
    error: BaseException,
) -> dict[str, object]:
    return {
        "id": item.id,
        "expected_answer": item.answer,
        "baseline_answer_exact_match": 0.0,
        "baseline_answer_f1": 0.0,
        "baseline_answer_containment": 0.0,
        "baseline_supporting_document_recall": 0.0,
        "baseline_retrieval_count": 0,
        "baseline_chat_calls": 0,
        "baseline_answer": "",
        "enhanced_answer_exact_match": 0.0,
        "enhanced_answer_f1": 0.0,
        "enhanced_answer_containment": 0.0,
        "enhanced_supporting_document_recall": 0.0,
        "enhanced_retrieval_count": 0,
        "enhanced_chat_calls": 0,
        "enhanced_answer": "",
        "error": f"{type(error).__name__}: {error}"[:1000],
    }


async def run_chartqa_benchmark(
    questions: Sequence[ChartQABenchmarkQuestion],
    *,
    parser: ParserProtocol,
    chat_client: ChatProtocol,
    max_concurrency: int = 3,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ChartQABenchmarkResult:
    semaphore = asyncio.Semaphore(max(max_concurrency, 1))
    retrying_chat = RetryingChatClient(chat_client)
    completed = 0
    total = len(questions)

    async with httpx.AsyncClient(timeout=120.0) as client:

        async def evaluate(item: ChartQABenchmarkQuestion) -> dict[str, object]:
            nonlocal completed
            async with semaphore:
                baseline_latency_ms = 0.0
                baseline_answer = ""
                errors: list[str] = []
                try:
                    baseline_started = time.perf_counter()
                    baseline_completion = await retrying_chat.complete(
                        [
                            ChatMessage(
                                role="system",
                                content=(
                                    "Return only the shortest answer to the chart question. "
                                    "No chart content is available."
                                ),
                            ),
                            ChatMessage(role="user", content=item.question),
                        ]
                    )
                    baseline_latency_ms = (time.perf_counter() - baseline_started) * 1000
                    baseline_answer = baseline_completion.content.strip()
                except Exception as exc:  # noqa: BLE001 - isolate one benchmark row
                    errors.append(f"baseline {type(exc).__name__}: {exc}"[:500])

                parser_latency_ms = 0.0
                enhanced_latency_ms = 0.0
                enhanced_answer = ""
                context = ""
                asset_count = 0
                try:
                    response = await client.get(item.image_url)
                    response.raise_for_status()
                    pdf_content = image_to_pdf(response.content)
                    parser_started = time.perf_counter()
                    parsed = await parser.parse_pdf(f"{item.id}.pdf", pdf_content)
                    parser_latency_ms = (time.perf_counter() - parser_started) * 1000
                    context = _parsed_text(parsed)
                    asset_count = len(parsed.assets)
                    chat_started = time.perf_counter()
                    answer = await retrying_chat.complete(
                        [
                            ChatMessage(
                                role="system",
                                content=(
                                    "Answer the chart question using only the extracted document "
                                    "text. Return only the short answer, with no explanation."
                                ),
                            ),
                            ChatMessage(
                                role="user",
                                content=(
                                    f"Question: {item.question}\nExtracted chart text:\n{context}"
                                ),
                            ),
                        ]
                    )
                    enhanced_latency_ms = (time.perf_counter() - chat_started) * 1000
                    enhanced_answer = answer.content.strip()
                except Exception as exc:  # noqa: BLE001 - retain the remaining benchmark rows
                    errors.append(f"enhanced {type(exc).__name__}: {exc}"[:500])

                completed += 1
                if progress_callback is not None:
                    progress_callback(completed, total)
                return {
                    "id": item.id,
                    "baseline_answer_accuracy": float(
                        any(_answer_equal(baseline_answer, expected) for expected in item.answers)
                    ),
                    "baseline_chat_latency_ms": baseline_latency_ms,
                    "baseline_answer": baseline_answer,
                    "enhanced_answer_accuracy": float(
                        bool(context)
                        and any(
                            _answer_equal(enhanced_answer, expected) for expected in item.answers
                        )
                    ),
                    "enhanced_chat_latency_ms": enhanced_latency_ms,
                    "enhanced_answer": enhanced_answer,
                    "parse_success": 1.0 if context else 0.0,
                    "asset_extraction_success": 1.0 if asset_count else 0.0,
                    "asset_count": asset_count,
                    "parser_latency_ms": parser_latency_ms,
                    "expected_answers": item.answers,
                    "error": " | ".join(errors)[:1000],
                }

        rows = list(await asyncio.gather(*(evaluate(item) for item in questions)))

    baseline = ChartQAModeMetrics(
        answer_accuracy=_average(row["baseline_answer_accuracy"] for row in rows),
        document_parse_success_rate=0.0,
        asset_extraction_rate=0.0,
        average_chat_latency_ms=_average(row["baseline_chat_latency_ms"] for row in rows),
    )
    enhanced = ChartQAModeMetrics(
        answer_accuracy=_average(row["enhanced_answer_accuracy"] for row in rows),
        document_parse_success_rate=_average(row["parse_success"] for row in rows),
        asset_extraction_rate=_average(row["asset_extraction_success"] for row in rows),
        average_chat_latency_ms=_average(row["enhanced_chat_latency_ms"] for row in rows),
    )
    return ChartQABenchmarkResult(
        dataset_size=len(rows),
        baseline=baseline,
        enhanced=enhanced,
        improvement={
            "answer_accuracy": enhanced.answer_accuracy - baseline.answer_accuracy,
            "document_parse_success_rate": (
                enhanced.document_parse_success_rate - baseline.document_parse_success_rate
            ),
            "asset_extraction_rate": (
                enhanced.asset_extraction_rate - baseline.asset_extraction_rate
            ),
        },
        parse_success_rate=_average(row["parse_success"] for row in rows),
        average_parser_latency_ms=_average(row["parser_latency_ms"] for row in rows),
        questions=rows,
    )


def image_to_pdf(content: bytes) -> bytes:
    """Create a single-page PDF from a PNG or JPEG without extra dependencies."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height, rgb = _decode_png_rgb(content)
        image_dictionary = (
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {{length}} >>"
        ).encode("ascii")
        image_stream = zlib.compress(rgb)
    elif content.startswith(b"\xff\xd8\xff"):
        width, height, components = _jpeg_dimensions(content)
        color_space = "/DeviceGray" if components == 1 else "/DeviceRGB"
        image_dictionary = (
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
            f"/ColorSpace {color_space} /BitsPerComponent 8 /Filter /DCTDecode "
            "/Length {length} >>"
        ).encode("ascii")
        image_stream = content
    else:
        raise ValueError("ChartQA image must be PNG or JPEG")

    content_stream = f"q\n{width} 0 0 {height} 0 0 cm\n/Im0 Do\nQ\n".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            "/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        image_dictionary.replace(b"{length}", str(len(image_stream)).encode("ascii"))
        + b"\nstream\n"
        + image_stream
        + b"\nendstream",
        f"<< /Length {len(content_stream)} >>\nstream\n".encode("ascii")
        + content_stream
        + b"endstream",
    ]
    return _pdf_from_objects(objects)


def _pdf_from_objects(objects: Sequence[bytes]) -> bytes:
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    )
    output.extend(trailer.encode("ascii"))
    return bytes(output)


def _decode_png_rgb(content: bytes) -> tuple[int, int, bytes]:
    position = 8
    width = height = bit_depth = color_type = interlace = 0
    compressed = bytearray()
    while position + 8 <= len(content):
        size = struct.unpack(">I", content[position : position + 4])[0]
        kind = content[position + 4 : position + 8]
        data = content[position + 8 : position + 8 + size]
        position += size + 12
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", data)
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            break
    if not width or not height or bit_depth != 8 or interlace != 0:
        raise ValueError("unsupported PNG encoding; expected non-interlaced 8-bit PNG")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError("unsupported PNG color type")
    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    rows: list[bytes] = []
    previous = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        encoded = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        decoded = _unfilter(encoded, previous, channels, filter_type)
        rows.append(bytes(decoded))
        previous = decoded
    rgb = bytearray()
    for row in rows:
        for index in range(0, len(row), channels):
            if color_type == 0:
                rgb.extend((row[index],) * 3)
            elif color_type == 2:
                rgb.extend(row[index : index + 3])
            elif color_type == 4:
                rgb.extend((row[index],) * 3)
            else:
                rgb.extend(row[index : index + 3])
    return width, height, bytes(rgb)


def _unfilter(row: bytearray, previous: bytearray, bpp: int, filter_type: int) -> bytearray:
    for index in range(len(row)):
        left = row[index - bpp] if index >= bpp else 0
        up = previous[index]
        up_left = previous[index - bpp] if index >= bpp else 0
        if filter_type == 1:
            row[index] = (row[index] + left) & 0xFF
        elif filter_type == 2:
            row[index] = (row[index] + up) & 0xFF
        elif filter_type == 3:
            row[index] = (row[index] + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            row[index] = (row[index] + _paeth(left, up, up_left)) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"unsupported PNG filter type: {filter_type}")
    return row


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    distances = (abs(estimate - left), abs(estimate - up), abs(estimate - up_left))
    return (left, up, up_left)[distances.index(min(distances))]


def _jpeg_dimensions(content: bytes) -> tuple[int, int, int]:
    position = 2
    while position + 9 < len(content):
        if content[position] != 0xFF:
            position += 1
            continue
        marker = content[position + 1]
        position += 2
        if marker in {0xD8, 0xD9}:
            continue
        if position + 2 > len(content):
            break
        length = struct.unpack(">H", content[position : position + 2])[0]
        if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(
            range(0xCD, 0xD0)
        ):
            if length < 8:
                break
            height, width, components = struct.unpack(">HHB", content[position + 3 : position + 8])
            return width, height, components
        position += length
    raise ValueError("JPEG dimensions could not be detected")


def _parsed_text(parsed: ParsedDocument) -> str:
    if parsed.markdown and parsed.markdown.strip():
        return parsed.markdown.strip()
    return "\n".join(block.text.strip() for block in parsed.blocks if block.text.strip())


def _evidence_list(value: object) -> list[AgentEvidence]:
    if not isinstance(value, list):
        return []
    return [item for item in cast(list[object], value) if isinstance(item, AgentEvidence)]


def _set_recall(expected: set[str], actual: set[str]) -> float:
    return len(expected & actual) / len(expected) if expected else 0.0


def _rag_answer_prompt(question: str, evidence: Sequence[AgentEvidence]) -> str:
    evidence_lines = [
        (f"[{item.label}] Title: {item.metadata.get('title', item.filename)}\n{item.text}")
        for item in evidence
    ]
    return "\n\n".join(
        [
            f"Question: {question}",
            "Evidence:",
            *(evidence_lines or ["No evidence retrieved."]),
        ]
    )


def _exact_match(predicted: str, expected: str) -> float:
    return float(_normalize_answer(predicted) == _normalize_answer(expected))


def _answer_equal(predicted: str, expected: str) -> bool:
    if _normalize_answer(predicted) == _normalize_answer(expected):
        return True
    predicted_number = _chart_number(predicted)
    expected_number = _chart_number(expected)
    if predicted_number is None or expected_number is None:
        return False
    tolerance = 0.05 * abs(expected_number)
    if expected_number == 0:
        tolerance = 1e-9
    return abs(predicted_number - expected_number) <= tolerance


def _answer_contains(predicted: str, expected: str) -> float:
    normalized_predicted = _normalize_answer(predicted)
    normalized_expected = _normalize_answer(expected)
    if not normalized_expected:
        return 0.0
    return float(normalized_expected in normalized_predicted)


def _chart_number(value: str) -> float | None:
    candidate = value.strip().replace(",", "").replace("$", "").rstrip("%")
    try:
        return float(candidate)
    except ValueError:
        return None


def _token_f1(predicted: str, expected: str) -> float:
    predicted_tokens = _normalize_answer(predicted).split()
    expected_tokens = _normalize_answer(expected).split()
    if not predicted_tokens or not expected_tokens:
        return float(predicted_tokens == expected_tokens)
    overlap = Counter(predicted_tokens) & Counter(expected_tokens)
    common = sum(overlap.values())
    if common == 0:
        return 0.0
    precision = common / len(predicted_tokens)
    recall = common / len(expected_tokens)
    return 2 * precision * recall / (precision + recall)


def _normalize_answer(value: str) -> str:
    normalized = value.lower()
    normalized = re.sub(r"\[s\d+\]", " ", normalized)
    normalized = normalized.replace("**", "").replace("__", "")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\b(a|an|the)\b", " ", normalized)
    return " ".join(normalized.split())


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float | str):
        return int(value)
    return 0


def _average(values: Iterable[object]) -> float:
    numbers = [_float_value(value) for value in values]
    return sum(numbers) / len(numbers) if numbers else 0.0


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float | str):
        return float(value)
    return 0.0
