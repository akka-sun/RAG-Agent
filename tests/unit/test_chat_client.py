import json

import httpx
import pytest

from app.infrastructure.chat_client import ChatClient, ChatMessage, ExternalModelError


@pytest.mark.asyncio
async def test_chat_client_posts_openai_compatible_messages() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "answer"}}],
                "usage": {"total_tokens": 12},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ChatClient(
            base_url="https://api.example.test/v1",
            api_key="key",
            model="chat-model",
            http_client=http_client,
        )

        result = await client.complete([ChatMessage(role="user", content="hello")])

    assert result.content == "answer"
    assert result.total_tokens == 12
    assert captured_request is not None
    assert str(captured_request.url) == "https://api.example.test/v1/chat/completions"
    assert captured_request.headers["authorization"] == "Bearer key"
    assert json.loads(captured_request.content) == {
        "model": "chat-model",
        "messages": [{"role": "user", "content": "hello"}],
        "temperature": 0,
    }


@pytest.mark.asyncio
async def test_chat_client_raises_external_model_error_for_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "rate limit"}},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = ChatClient(
            base_url="https://api.example.test/v1",
            api_key="key",
            model="chat-model",
            http_client=http_client,
        )

        with pytest.raises(ExternalModelError) as exc_info:
            await client.complete([ChatMessage(role="user", content="hello")])

    error = exc_info.value
    assert error.service_name == "chat"
    assert error.status_code == 429
    assert "rate limit" in str(error)
