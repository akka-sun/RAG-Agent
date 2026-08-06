import json
from uuid import UUID

import pytest

from app.infrastructure.redis_index import RedisDocumentIndex
from app.rag.types import IndexedChunk

KB = UUID("11111111-1111-1111-1111-111111111111")
DOC = UUID("22222222-2222-2222-2222-222222222222")


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    def set(self, name: str, value: str) -> None:
        self.calls.append(("set", name))
        self.data[name] = value

    def get(self, name: str) -> str | None:
        self.calls.append(("get", name))
        return self.data.get(name)

    def delete(self, name: str) -> int:
        self.calls.append(("delete", name))
        return int(self.data.pop(name, None) is not None)


def chunk(text: str, i: int = 0) -> IndexedChunk:
    return IndexedChunk(KB, DOC, "a.txt", str(i), text, i, i + 1, (0.1, 0.2))


@pytest.mark.asyncio
async def test_replace_round_trip_and_overwrites() -> None:
    redis = FakeRedis()
    index = RedisDocumentIndex(redis)
    await index.replace_document(KB, DOC, [chunk("first")])
    await index.replace_document(KB, DOC, [chunk("second", 1)])
    assert await index.get_document(KB, DOC) == [chunk("second", 1)]
    assert redis.calls[0] == ("set", f"rag:index:{KB}:{DOC}")
    assert isinstance(json.loads(redis.data[f"rag:index:{KB}:{DOC}"]), list)


@pytest.mark.asyncio
async def test_isolates_keys_and_delete_missing() -> None:
    redis = FakeRedis()
    index = RedisDocumentIndex(redis)
    other = UUID("33333333-3333-3333-3333-333333333333")
    await index.replace_document(KB, DOC, [chunk("a")])
    await index.replace_document(other, DOC, [chunk("b")])
    assert (await index.get_document(KB, DOC))[0].text == "a"
    await index.delete_document(KB, DOC)
    assert await index.get_document(KB, DOC) == []
    await index.delete_document(KB, DOC)


@pytest.mark.asyncio
async def test_redis_errors_propagate() -> None:
    class Broken(FakeRedis):
        def get(self, name: str) -> None:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await RedisDocumentIndex(Broken()).get_document(KB, DOC)
