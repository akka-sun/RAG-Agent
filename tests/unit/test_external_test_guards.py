import pytest

from tests.conftest import external_tests_enabled, skip_unless_external_enabled


def test_external_guard_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAG_AGENT_EXTERNAL_TESTS_ENABLED", raising=False)

    assert external_tests_enabled() is False


def test_external_guard_accepts_enabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_AGENT_EXTERNAL_TESTS_ENABLED", "true")

    assert external_tests_enabled() is True
    skip_unless_external_enabled("non-empty")
