from __future__ import annotations

from app.evaluation.runner import EvaluationResult


def render_markdown_report(result: EvaluationResult) -> str:
    lines = [
        "# RAG Evaluation Report",
        "",
        f"- Dataset size: {result.dataset_size}",
        "",
        "| Mode | Recall@K | MRR | Citation Hit Rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for mode, metrics in result.mode_results.items():
        row = (
            f"| {mode.title()} | {metrics.recall_at_k:.3f} | "
            f"{metrics.mrr:.3f} | {metrics.citation_hit_rate:.3f} |"
        )
        lines.append(row)

    lines.extend(["", "## Question-level details", ""])
    for question in result.question_results:
        lines.append(f"### {question.question_id}")
        lines.append(question.question)
        lines.append("")
        for mode, metrics in question.mode_results.items():
            line = (
                f"- {mode}: recall@k={metrics.recall_at_k:.3f}, "
                f"mrr={metrics.mrr:.3f}, "
                f"citation_hit_rate={metrics.citation_hit_rate:.3f}"
            )
            lines.append(line)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
