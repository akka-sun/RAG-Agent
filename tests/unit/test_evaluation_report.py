from app.evaluation.report import render_markdown_report
from app.evaluation.runner import EvaluationResult, ModeEvaluationResult, QuestionEvaluationResult


def fake_evaluation_result() -> EvaluationResult:
    return EvaluationResult(
        dataset_size=1,
        mode_results={
            "dense": ModeEvaluationResult(0.5, 0.5, 0.5),
            "bm25": ModeEvaluationResult(0.6, 0.4, 0.7),
            "rrf": ModeEvaluationResult(0.7, 0.6, 0.8),
            "rerank": ModeEvaluationResult(0.9, 0.8, 1.0),
        },
        question_results=[
            QuestionEvaluationResult(
                question_id="q1",
                question="retention",
                mode_results={
                    "dense": ModeEvaluationResult(0.5, 0.5, 0.5),
                    "bm25": ModeEvaluationResult(0.6, 0.4, 0.7),
                    "rrf": ModeEvaluationResult(0.7, 0.6, 0.8),
                    "rerank": ModeEvaluationResult(0.9, 0.8, 1.0),
                },
            )
        ],
    )


def test_report_includes_mode_table() -> None:
    report = render_markdown_report(fake_evaluation_result())

    assert "| Mode | Recall@K | MRR | Citation Hit Rate |" in report
    assert "Dense" in report
    assert "Rerank" in report
