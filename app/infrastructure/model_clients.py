from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import cast

import httpx

from app.rag.hybrid import RankedChunk


class EmbeddingClient:
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

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        self._validate_config("embedding")

        response = await self._post(
            _join_url(self._base_url, "embeddings"),
            {
                "model": self._model,
                "input": list(texts),
            },
        )
        data = _json_mapping(response)
        embeddings = data.get("data")
        if not isinstance(embeddings, list):
            msg = "embedding response must contain a data list"
            raise ValueError(msg)
        return [_embedding_from_item(item) for item in embeddings]

    async def _post(self, url: str, payload: Mapping[str, object]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if self._http_client is not None:
            response = await self._http_client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response

    def _validate_config(self, purpose: str) -> None:
        if not self._base_url or not self._model or not self._api_key:
            msg = f"{purpose} client requires base_url, model, and api_key"
            raise ValueError(msg)


class RerankerClient:
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

    async def rerank(
        self,
        query: str,
        chunks: Sequence[RankedChunk],
        limit: int,
    ) -> list[RankedChunk]:
        if not chunks or limit <= 0:
            return []
        self._validate_config("reranker")

        response = await self._post(
            _rerank_url(self._base_url),
            {
                "model": self._model,
                "query": query,
                "documents": [chunk.text for chunk in chunks],
                "top_n": limit,
            },
        )
        data = _json_mapping(response)
        results = data.get("results", data.get("data"))
        if not isinstance(results, list):
            msg = "reranker response must contain a results or data list"
            raise ValueError(msg)

        reranked: list[RankedChunk] = []
        for item in results:
            if not isinstance(item, Mapping):
                continue
            index = _int_value(item.get("index"))
            if index is None or index < 0 or index >= len(chunks):
                continue
            score = _float_value(
                item.get("relevance_score", item.get("score", item.get("rerank_score", 0.0)))
            )
            reranked.append(replace(chunks[index], rerank_score=score))

        return sorted(
            reranked,
            key=lambda chunk: (-(chunk.rerank_score or 0.0), chunk.chunk_id),
        )[:limit]

    async def _post(self, url: str, payload: Mapping[str, object]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if self._http_client is not None:
            response = await self._http_client.post(url, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response

    def _validate_config(self, purpose: str) -> None:
        if not self._base_url or not self._model or not self._api_key:
            msg = f"{purpose} client requires base_url, model, and api_key"
            raise ValueError(msg)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _rerank_url(base_url: str) -> str:
    if base_url.endswith("/rerank"):
        return base_url
    return _join_url(base_url, "rerank")


def _json_mapping(response: httpx.Response) -> Mapping[str, object]:
    data = response.json()
    if not isinstance(data, Mapping):
        msg = "model API response must be a JSON object"
        raise ValueError(msg)
    return cast(Mapping[str, object], data)


def _embedding_from_item(item: object) -> list[float]:
    if not isinstance(item, Mapping):
        msg = "embedding item must be a JSON object"
        raise ValueError(msg)
    embedding = item.get("embedding")
    if not isinstance(embedding, list):
        msg = "embedding item must contain an embedding list"
        raise ValueError(msg)
    return [_float_value(value) for value in embedding]


def _int_value(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value:
        return int(value)
    return None


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value:
        return float(value)
    return 0.0
