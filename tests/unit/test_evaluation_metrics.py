from app.evaluation.metrics import citation_hit_rate, mrr, recall_at_k


def test_recall_at_k_counts_expected_documents_in_top_k() -> None:
    assert recall_at_k({"a", "b"}, ["c", "a", "b"], k=2) == 0.5


def test_mrr_returns_inverse_first_relevant_rank() -> None:
    assert mrr({"b"}, ["a", "b", "c"]) == 0.5


def test_citation_hit_rate_requires_expected_citation_match() -> None:
    assert citation_hit_rate({"doc1#chunk1"}, {"doc1#chunk1", "doc2#chunk9"}) == 1.0
