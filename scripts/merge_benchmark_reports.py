from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge partitioned benchmark JSON reports")
    parser.add_argument("--kind", choices=("agentic", "chartqa"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()

    key = "hotpotqa_agentic_rag" if args.kind == "agentic" else "chartqa_image_pdf"
    parts = [_load_part(path, key) for path in args.inputs]
    merged = _merge(parts, key=key, kind=args.kind, sources=args.inputs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({key: merged}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Merged {merged['dataset_size']} rows into {args.output}")


def _load_part(path: Path, key: str) -> Mapping[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path} does not contain {key}")
    candidate = cast(Mapping[object, object], raw).get(key)
    if not isinstance(candidate, Mapping):
        raise ValueError(f"{path} does not contain {key}")
    return cast(Mapping[str, Any], candidate)


def _merge(
    parts: Sequence[Mapping[str, Any]],
    *,
    key: str,
    kind: str,
    sources: Sequence[Path],
) -> dict[str, object]:
    total = sum(int(part["dataset_size"]) for part in parts)
    if total <= 0:
        raise ValueError("merged benchmark must contain at least one row")
    rows = [
        cast(dict[str, object], row)
        for part in parts
        for row in cast(list[object], part.get("questions", []))
        if isinstance(row, dict)
    ]
    ids = [str(row.get("id", "")) for row in rows]
    if len(rows) != total:
        raise ValueError(f"expected {total} question rows, found {len(rows)}")
    if len(set(ids)) != len(ids):
        raise ValueError("merged benchmark contains duplicate question IDs")

    baseline = _weighted_mapping(parts, "baseline", total)
    enhanced = _weighted_mapping(parts, "enhanced", total)
    result: dict[str, object] = {
        "dataset_size": total,
        "baseline": baseline,
        "enhanced": enhanced,
        "improvement": {
            metric: enhanced[metric] - baseline[metric]
            for metric in baseline.keys() & enhanced.keys()
            if metric not in {"average_chat_latency_ms", "average_chat_calls", "average_retrievals"}
        },
        "failed_samples": sum(bool(row.get("error")) for row in rows),
        "source_parts": [str(path) for path in sources],
        "questions": rows,
    }
    if kind == "chartqa":
        result["parse_success_rate"] = _weighted_scalar(parts, "parse_success_rate", total)
        result["average_parser_latency_ms"] = _weighted_scalar(
            parts,
            "average_parser_latency_ms",
            total,
        )
    result["benchmark"] = key
    return result


def _weighted_mapping(
    parts: Sequence[Mapping[str, Any]],
    key: str,
    total: int,
) -> dict[str, float]:
    metric_names = {
        str(metric) for part in parts for metric in cast(Mapping[str, object], part[key])
    }
    return {
        metric: sum(
            _number(cast(Mapping[str, object], part[key]).get(metric, 0.0))
            * int(part["dataset_size"])
            for part in parts
        )
        / total
        for metric in sorted(metric_names)
    }


def _weighted_scalar(parts: Sequence[Mapping[str, Any]], key: str, total: int) -> float:
    return sum(_number(part.get(key, 0.0)) * int(part["dataset_size"]) for part in parts) / total


def _number(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float | str):
        return float(value)
    raise TypeError(f"expected numeric metric, got {type(value).__name__}")


if __name__ == "__main__":
    main()
