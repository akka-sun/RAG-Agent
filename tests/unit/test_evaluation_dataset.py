import json
import tempfile
import uuid
from pathlib import Path

from app.evaluation.dataset import load_dataset


def test_load_dataset_validates_expected_documents() -> None:
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as temp_dir:
        path = Path(temp_dir) / "dataset.json"
        path.write_text(
            json.dumps(
                {
                    "questions": [
                        {
                            "id": "q1",
                            "question": "What is the retention policy?",
                            "expected_document_ids": [
                                "00000000-0000-0000-0000-000000000001",
                            ],
                            "expected_citations": [
                                {"document_id": "00000000-0000-0000-0000-000000000001"}
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        dataset = load_dataset(path)

        assert dataset.questions[0].id == "q1"
        assert dataset.questions[0].expected_document_ids[0] == uuid.UUID(
            "00000000-0000-0000-0000-000000000001"
        )
