from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.evaluation.dataset import EvaluationQuestion

HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"


@dataclass(frozen=True, slots=True)
class NanoSciFactBenchmark:
    corpus: dict[uuid.UUID, str]
    questions: list[EvaluationQuestion]


@dataclass(frozen=True, slots=True)
class HotpotContext:
    title: str
    text: str
    document_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class HotpotBenchmarkQuestion:
    id: str
    question: str
    answer: str
    context: list[HotpotContext]
    supporting_titles: set[str]


@dataclass(frozen=True, slots=True)
class ChartQABenchmarkQuestion:
    id: str
    image_url: str
    question: str
    answers: list[str]


async def fetch_huggingface_rows(
    *,
    dataset: str,
    config: str,
    split: str,
    limit: int | None = None,
    page_size: int = 100,
    timeout: float = 60.0,
    retries: int = 3,
) -> list[dict[str, Any]]:
    """Fetch rows through the public HF datasets-server API.

    This avoids requiring the optional `datasets` package and keeps benchmark
    downloads reproducible inside the existing application environment.
    """
    rows: list[dict[str, Any]] = []
    offset = 0
    async with httpx.AsyncClient(timeout=timeout) as client:
        while limit is None or len(rows) < limit:
            length = page_size if limit is None else min(page_size, limit - len(rows))
            response: httpx.Response | None = None
            for attempt in range(max(retries, 0) + 1):
                try:
                    response = await client.get(
                        HF_ROWS_URL,
                        params={
                            "dataset": dataset,
                            "config": config,
                            "split": split,
                            "offset": offset,
                            "length": length,
                        },
                    )
                    if response.status_code not in {502, 503, 504}:
                        break
                except httpx.RequestError:
                    if attempt >= retries:
                        raise
                if attempt < retries:
                    await asyncio.sleep(2**attempt)
            if response is None:
                raise RuntimeError("Hugging Face rows request returned no response")
            response.raise_for_status()
            raw_payload = response.json()
            if not isinstance(raw_payload, Mapping):
                raise ValueError("Hugging Face rows response must be an object")
            payload = cast(Mapping[str, object], raw_payload)
            raw_rows = payload.get("rows")
            if not isinstance(raw_rows, list):
                raise ValueError("Hugging Face rows response must contain rows")
            page: list[dict[str, Any]] = []
            for item in cast(list[object], raw_rows):
                if not isinstance(item, Mapping):
                    continue
                row = cast(Mapping[str, object], item).get("row")
                if isinstance(row, Mapping):
                    page.append(dict(cast(Mapping[str, Any], row)))
            if not page:
                break
            rows.extend(page)
            offset += len(page)
            if len(page) < length:
                break
    return rows[:limit] if limit is not None else rows


async def load_nanoscifact(
    *,
    query_limit: int | None = 50,
    corpus_limit: int | None = None,
) -> NanoSciFactBenchmark:
    dataset = "zeta-alpha-ai/NanoSciFact"
    corpus_rows, query_rows, qrel_rows = await _gather(
        fetch_huggingface_rows(dataset=dataset, config="corpus", split="train"),
        fetch_huggingface_rows(dataset=dataset, config="queries", split="train", limit=query_limit),
        fetch_huggingface_rows(dataset=dataset, config="qrels", split="train"),
    )
    all_corpus: dict[uuid.UUID, str] = {}
    corpus_by_source_id: dict[str, uuid.UUID] = {}
    for row in corpus_rows:
        source_id = _string(row.get("_id"))
        text = _string(row.get("text"))
        if not source_id or not text:
            continue
        document_id = benchmark_document_id("nanoscifact", source_id)
        corpus_by_source_id[source_id] = document_id
        all_corpus[document_id] = text

    selected_ids: set[str] | None = None
    if corpus_limit is not None:
        query_ids = {_string(item.get("_id")) for item in query_rows}
        relevant_ids = {
            _string(row.get("corpus-id"))
            for row in qrel_rows
            if _string(row.get("query-id")) in query_ids
        }
        selected_ids = set(relevant_ids)
        for row in corpus_rows:
            source_id = _string(row.get("_id"))
            if len(selected_ids) >= corpus_limit:
                break
            if source_id:
                selected_ids.add(source_id)
    corpus = {
        document_id: all_corpus[document_id]
        for source_id, document_id in corpus_by_source_id.items()
        if selected_ids is None or source_id in selected_ids
    }

    qrels: dict[str, list[uuid.UUID]] = defaultdict(list)
    for row in qrel_rows:
        query_id = _string(row.get("query-id"))
        corpus_id = _string(row.get("corpus-id"))
        document_id = corpus_by_source_id.get(corpus_id)
        if query_id and document_id is not None:
            qrels[query_id].append(document_id)

    questions: list[EvaluationQuestion] = []
    for row in query_rows:
        query_id = _string(row.get("_id"))
        query = _string(row.get("text"))
        if query_id and query:
            questions.append(
                EvaluationQuestion(
                    id=query_id,
                    question=query,
                    expected_document_ids=qrels.get(query_id, []),
                )
            )
    return NanoSciFactBenchmark(corpus=corpus, questions=questions)


async def load_hotpotqa(
    *,
    limit: int = 100,
) -> list[HotpotBenchmarkQuestion]:
    rows = await fetch_huggingface_rows(
        dataset="hotpotqa/hotpot_qa",
        config="distractor",
        split="validation",
        limit=limit,
    )
    result: list[HotpotBenchmarkQuestion] = []
    for index, row in enumerate(rows):
        question = _string(row.get("question"))
        answer = _string(row.get("answer"))
        if not question or not answer:
            continue
        contexts = _hotpot_contexts(row.get("context"))
        supporting_titles = _supporting_titles(row.get("supporting_facts"))
        result.append(
            HotpotBenchmarkQuestion(
                id=_string(row.get("id")) or f"hotpot-{index}",
                question=question,
                answer=answer,
                context=contexts,
                supporting_titles=supporting_titles,
            )
        )
    return result


async def load_chartqa(*, limit: int = 100, split: str = "test") -> list[ChartQABenchmarkQuestion]:
    rows = await fetch_huggingface_rows(
        dataset="HuggingFaceM4/ChartQA",
        config="default",
        split=split,
        limit=limit,
    )
    result: list[ChartQABenchmarkQuestion] = []
    for index, row in enumerate(rows):
        image = row.get("image")
        image_url = (
            cast(Mapping[str, object], image).get("src") if isinstance(image, Mapping) else None
        )
        question = _string(row.get("query"))
        labels = row.get("label")
        answers = (
            [str(item).strip() for item in cast(list[object], labels)]
            if isinstance(labels, list)
            else []
        )
        if isinstance(image_url, str) and image_url and question and answers:
            result.append(
                ChartQABenchmarkQuestion(
                    id=f"chartqa-{index}",
                    image_url=image_url,
                    question=question,
                    answers=answers,
                )
            )
    return result


def benchmark_document_id(dataset: str, source_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"https://huggingface.co/datasets/{dataset}/{source_id}")


async def _gather(*coroutines: Any) -> list[Any]:
    return list(await asyncio.gather(*coroutines))


def _hotpot_contexts(value: object) -> list[HotpotContext]:
    if not isinstance(value, Mapping):
        return []
    mapping = cast(Mapping[str, object], value)
    titles = mapping.get("title")
    sentences = mapping.get("sentences")
    if not isinstance(titles, list) or not isinstance(sentences, list):
        return []
    result: list[HotpotContext] = []
    for title_value, sentence_value in zip(
        cast(list[object], titles), cast(list[object], sentences), strict=False
    ):
        title = _string(title_value)
        if not title or not isinstance(sentence_value, list):
            continue
        sentence_items = cast(list[object], sentence_value)
        text = " ".join(_string(sentence) for sentence in sentence_items if _string(sentence))
        if text:
            result.append(
                HotpotContext(
                    title=title,
                    text=text,
                    document_id=benchmark_document_id("hotpotqa", title),
                )
            )
    return result


def _supporting_titles(value: object) -> set[str]:
    if not isinstance(value, Mapping):
        return set()
    titles = cast(Mapping[str, object], value).get("title")
    return (
        {_string(item) for item in cast(list[object], titles)}
        if isinstance(titles, list)
        else set()
    )


def _string(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return str(value).strip() if value is not None else ""
