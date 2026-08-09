import os

import pytest


def external_tests_enabled() -> bool:
    return os.getenv("RAG_AGENT_EXTERNAL_TESTS_ENABLED", "").casefold() == "true"


def skip_unless_external_enabled(*required_values: str) -> None:
    if not external_tests_enabled():
        pytest.skip("set RAG_AGENT_EXTERNAL_TESTS_ENABLED=true to call real external APIs")
    if any(not value for value in required_values):
        pytest.skip("external API test credentials are not fully configured")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if external_tests_enabled():
        return

    skip_marker = pytest.mark.skip(
        reason="set RAG_AGENT_EXTERNAL_TESTS_ENABLED=true to call real external APIs"
    )
    for item in items:
        if "external" in item.keywords:
            item.add_marker(skip_marker)
