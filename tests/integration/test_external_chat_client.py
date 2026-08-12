import os

import pytest

from app.config import Settings
from app.infrastructure.chat_client import ChatClient, ChatMessage


def external_tests_enabled() -> bool:
    return os.getenv("RAG_AGENT_EXTERNAL_TESTS_ENABLED", "").casefold() == "true"


def skip_unless_external_enabled(*required_values: str) -> None:
    if not external_tests_enabled():
        pytest.skip("set RAG_AGENT_EXTERNAL_TESTS_ENABLED=true to call real external APIs")
    if any(not value for value in required_values):
        pytest.skip("external API test credentials are not fully configured")


@pytest.mark.external
@pytest.mark.asyncio
async def test_chat_client_calls_real_api() -> None:
    settings = Settings()
    skip_unless_external_enabled(
        settings.chat_base_url,
        settings.chat_api_key,
        settings.chat_model,
    )
    client = ChatClient(
        base_url=settings.chat_base_url,
        api_key=settings.chat_api_key,
        model=settings.chat_model,
    )

    result = await client.complete(
        [ChatMessage(role="user", content="Reply with exactly: RAG Agent OK")]
    )

    assert result.content
