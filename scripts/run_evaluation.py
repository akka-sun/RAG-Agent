from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from app.api.dependencies import (
    get_embedding_client,
    get_milvus_chunk_store_instance,
    get_reranker_client,
)
from app.evaluation import EvaluationRunner, load_dataset, render_markdown_report


async def _run(dataset_path: Path, output_path: Path, knowledge_base_id: UUID, limit: int) -> None:
    dataset = load_dataset(dataset_path)
    runner = EvaluationRunner(
        knowledge_base_id=knowledge_base_id,
        store=get_milvus_chunk_store_instance(),
        embeddings=get_embedding_client(),
        reranker=get_reranker_client(),
        limit=limit,
    )
    result = await runner.run(dataset)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(result), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG retrieval evaluation")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--knowledge-base-id", type=UUID, required=True)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(_run(args.dataset, args.output, args.knowledge_base_id, args.limit))


if __name__ == "__main__":
    main()
