from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

import httpx

ChatRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str


@dataclass(frozen=True)
class ChatCompletionResult:
    content: str
    total_tokens: int | None = None


class ExternalModelError(RuntimeError):
    def __init__(
        self,
        *,
        service_name: str,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(f"{service_name} model request failed: {message}")
        self.service_name = service_name
        self.status_code = status_code


class ChatClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._http_client = http_client
        self._timeout = timeout

    async def complete(self, messages: Sequence[ChatMessage]) -> ChatCompletionResult:
        self._validate_config()
        response = await self._post(
            _join_url(self._base_url, "chat/completions"),
            {
                "model": self._model,
                "messages": [
                    {"role": message.role, "content": message.content} for message in messages
                ],
                "temperature": 0,
            },
        )
        data = _json_mapping(response)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            msg = "chat response must contain at least one choice"
            raise ValueError(msg)

        content = _message_content(choices[0])
        usage = data.get("usage")
        total_tokens = _total_tokens(usage)
        return ChatCompletionResult(content=content, total_tokens=total_tokens)

    async def _post(self, url: str, payload: Mapping[str, object]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            if self._http_client is not None:
                response = await self._http_client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise ExternalModelError(
                service_name="chat",
                message=str(exc),
            ) from exc

        if response.is_error:
            raise ExternalModelError(
                service_name="chat",
                status_code=response.status_code,
                message=_error_message(response),
            )
        return response

    def _validate_config(self) -> None:
        if not self._base_url or not self._model or not self._api_key:
            msg = "chat client requires base_url, model, and api_key"
            raise ValueError(msg)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _json_mapping(response: httpx.Response) -> Mapping[str, object]:
    data = response.json()
    if not isinstance(data, Mapping):
        msg = "chat API response must be a JSON object"
        raise ValueError(msg)
    return cast(Mapping[str, object], data)


def _message_content(choice: object) -> str:
    if not isinstance(choice, Mapping):
        msg = "chat choice must be a JSON object"
        raise ValueError(msg)
    choice_mapping = cast(Mapping[str, object], choice)
    message = choice_mapping.get("message")
    if not isinstance(message, Mapping):
        msg = "chat choice must contain a message object"
        raise ValueError(msg)
    message_mapping = cast(Mapping[str, object], message)
    content = message_mapping.get("content")
    if not isinstance(content, str):
        msg = "chat message content must be a string"
        raise ValueError(msg)
    return content


def _total_tokens(usage: object) -> int | None:
    if not isinstance(usage, Mapping):
        return None
    usage_mapping = cast(Mapping[str, object], usage)
    value = usage_mapping.get("total_tokens")
    if isinstance(value, int):
        return value
    return None


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:200]
    if not isinstance(data, Mapping):
        return response.text[:200]
    data_mapping = cast(Mapping[str, object], data)
    error = data_mapping.get("error")
    if isinstance(error, Mapping):
        error_mapping = cast(Mapping[str, object], error)
        message = error_mapping.get("message")
        if isinstance(message, str) and message:
            return message[:200]
    message = data_mapping.get("message")
    if isinstance(message, str) and message:
        return message[:200]
    return response.text[:200]
