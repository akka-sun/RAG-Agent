from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.api.dependencies import get_chat_client, get_embedding_client, get_reranker_client
from app.config import get_settings
from app.evaluation.benchmark_datasets import load_chartqa, load_hotpotqa, load_nanoscifact
from app.evaluation.benchmark_runner import (
    run_agentic_benchmark,
    run_chartqa_benchmark,
    run_retrieval_benchmark,
)
from app.parsers.mineru import MinerUParser
from app.parsers.paddlex import PaddleXParser


async def _run(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    mode = args.mode
    _validate_environment(settings, mode, args.pdf_parser)
    embeddings = get_embedding_client()
    chat = get_chat_client()
    results: dict[str, object] = {}

    if mode in {"all", "retrieval"}:
        retrieval_dataset = await load_nanoscifact(
            query_limit=args.retrieval_queries,
            corpus_limit=args.retrieval_corpus,
        )
        retrieval_result = await run_retrieval_benchmark(
            retrieval_dataset,
            embeddings=embeddings,
            reranker=get_reranker_client(),
            top_k=args.top_k,
            embedding_batch_size=args.embedding_batch_size,
        )
        results["nanoscifact_retrieval"] = _evaluation_result_dict(
            retrieval_result,
            corpus_size=len(retrieval_dataset.corpus),
        )

    if mode in {"all", "agentic"}:
        hotpot_questions = await load_hotpotqa(limit=args.agentic_offset + args.agentic_questions)
        hotpot_questions = hotpot_questions[args.agentic_offset :]
        agentic_result = await run_agentic_benchmark(
            hotpot_questions,
            embeddings=embeddings,
            reranker=get_reranker_client(),
            chat_client=chat,
            top_k=min(args.top_k, 3),
            max_retrievals=args.max_retrievals,
            embedding_batch_size=args.embedding_batch_size,
            max_concurrency=args.agentic_concurrency,
            progress_callback=_progress("HotpotQA"),
        )
        results["hotpotqa_agentic_rag"] = _dataclass_dict(agentic_result)

    if mode in {"all", "chartqa"}:
        chart_questions = await load_chartqa(limit=args.image_offset + args.image_questions)
        chart_questions = chart_questions[args.image_offset :]
        parser = _build_parser(settings, args.pdf_parser)
        chart_result = await run_chartqa_benchmark(
            chart_questions,
            parser=parser,
            chat_client=chat,
            max_concurrency=args.chartqa_concurrency,
            progress_callback=_progress("ChartQA"),
        )
        results["chartqa_image_pdf"] = _dataclass_dict(chart_result)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run real-model retrieval, Agentic RAG, and image/PDF benchmarks"
    )
    parser.add_argument(
        "--mode",
        choices=("all", "retrieval", "agentic", "chartqa"),
        default="all",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retrieval-queries", type=int, default=50)
    parser.add_argument("--retrieval-corpus", type=int, default=None)
    parser.add_argument("--agentic-questions", type=int, default=25)
    parser.add_argument("--agentic-offset", type=int, default=0)
    parser.add_argument("--image-questions", type=int, default=25)
    parser.add_argument("--image-offset", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-retrievals", type=int, default=3)
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    parser.add_argument("--agentic-concurrency", type=int, default=4)
    parser.add_argument("--chartqa-concurrency", type=int, default=3)
    parser.add_argument("--pdf-parser", choices=("mineru", "paddlex"), default=None)
    args = parser.parse_args()
    results = asyncio.run(_run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Benchmark report written to {args.output}")


def _build_parser(settings: Any, requested: str | None) -> Any:
    parser_name = requested or settings.default_pdf_parser
    if parser_name == "mineru":
        return MinerUParser(
            base_url=settings.mineru_base_url,
            api_key=settings.mineru_api_key,
            model_version=settings.mineru_model_version,
        )
    return PaddleXParser(base_url=settings.paddlex_base_url)


def _validate_environment(settings: Any, mode: str, pdf_parser: str | None) -> None:
    missing: list[str] = []
    if mode in {"all", "retrieval", "agentic"}:
        for name, value in (
            ("RAG_AGENT_EMBEDDING_API_KEY", settings.embedding_api_key),
            ("RAG_AGENT_EMBEDDING_BASE_URL", settings.embedding_base_url),
            ("RAG_AGENT_EMBEDDING_MODEL", settings.embedding_model),
            ("RAG_AGENT_RERANK_API_KEY", settings.rerank_api_key),
            ("RAG_AGENT_RERANK_BASE_URL", settings.rerank_base_url),
            ("RAG_AGENT_RERANK_MODEL", settings.rerank_model),
        ):
            if not value:
                missing.append(name)
    if mode in {"all", "agentic", "chartqa"}:
        for name, value in (
            ("RAG_AGENT_CHAT_API_KEY", settings.chat_api_key),
            ("RAG_AGENT_CHAT_BASE_URL", settings.chat_base_url),
            ("RAG_AGENT_CHAT_MODEL", settings.chat_model),
        ):
            if not value:
                missing.append(name)
    if mode in {"all", "chartqa"}:
        parser_name = pdf_parser or settings.default_pdf_parser
        parser_url = (
            settings.mineru_base_url if parser_name == "mineru" else settings.paddlex_base_url
        )
        if not parser_url:
            missing.append(
                "RAG_AGENT_MINERU_BASE_URL"
                if parser_name == "mineru"
                else "RAG_AGENT_PADDLEX_BASE_URL"
            )
        if parser_name == "mineru" and "mineru.net" in parser_url and not settings.mineru_api_key:
            missing.append("RAG_AGENT_MINERU_API_KEY")
    if missing:
        joined = ", ".join(sorted(set(missing)))
        raise SystemExit(f"Missing required benchmark configuration: {joined}")


def _evaluation_result_dict(result: Any, *, corpus_size: int) -> dict[str, object]:
    baseline = result.mode_results["bm25"]
    enhanced = result.mode_results["rerank"]
    return {
        "dataset_size": result.dataset_size,
        "corpus_size": corpus_size,
        "comparison": {
            "baseline": {
                "name": "bm25_only",
                "recall_at_k": baseline.recall_at_k,
                "mrr": baseline.mrr,
            },
            "enhanced": {
                "name": "dense_bm25_rrf_qwen3_rerank",
                "recall_at_k": enhanced.recall_at_k,
                "mrr": enhanced.mrr,
            },
            "absolute_improvement": {
                "recall_at_k": enhanced.recall_at_k - baseline.recall_at_k,
                "mrr": enhanced.mrr - baseline.mrr,
            },
            "relative_improvement_percent": {
                "recall_at_k": _relative_improvement(
                    baseline.recall_at_k,
                    enhanced.recall_at_k,
                ),
                "mrr": _relative_improvement(baseline.mrr, enhanced.mrr),
            },
        },
        "mode_results": {
            mode: {
                "recall_at_k": metrics.recall_at_k,
                "mrr": metrics.mrr,
                "citation_hit_rate": metrics.citation_hit_rate,
            }
            for mode, metrics in result.mode_results.items()
        },
    }


def _relative_improvement(baseline: float, enhanced: float) -> float:
    return ((enhanced - baseline) / baseline * 100) if baseline else 0.0


def _progress(name: str) -> Any:
    def report(completed: int, total: int) -> None:
        if completed == total or completed % 10 == 0:
            print(f"{name}: {completed}/{total}", flush=True)

    return report


def _dataclass_dict(value: Any) -> dict[str, object]:
    from dataclasses import asdict

    return asdict(value)


if __name__ == "__main__":
    main()
