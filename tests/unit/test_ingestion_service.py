import json
import uuid
from typing import Any

import pytest

from app.core.exceptions import DocumentCleanupFailedError
from app.models.document import DocumentStatus
from app.models.ingestion_task import TaskStage, TaskStatus
from app.services import ingestion as ingestion_module
from app.services.ingestion import IngestionService


class Obj:
    pass


class Session:
    def __init__(self, factory: Any, task: Any, document: Any) -> None:
        self.factory = factory
        self.task = task
        self.document = document

    async def __aenter__(self) -> "Session":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def get(self, model: type[Any], _ident: object) -> Any:
        return self.task if model.__name__ == "IngestionTask" else self.document

    async def commit(self) -> None:
        self.factory.commits.append(
            (
                self.task.stage,
                self.task.progress,
                self.document.status,
                self.document.parsed_object_key,
            )
        )
        if self.factory.fail_compensation and self.task.status == TaskStatus.FAILED:
            raise RuntimeError("compensation commit failed")

    async def rollback(self) -> None:
        self.factory.rollbacks += 1


class Factory:
    def __init__(self, task: Any, document: Any, *, fail_compensation: bool = False) -> None:
        self.task = task
        self.document = document
        self.fail_compensation = fail_compensation
        self.sessions: list[Session] = []
        self.commits: list[tuple[Any, int, Any, str | None]] = []
        self.rollbacks = 0

    def __call__(self) -> Session:
        session = Session(self, self.task, self.document)
        self.sessions.append(session)
        return session


class Repo:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def get(self, _task_id: object) -> Any:
        return self.session.task

    async def claim_pending(self, _task_id: object) -> Any | None:
        if self.session.task.status != TaskStatus.PENDING:
            return None
        self.session.task.status = TaskStatus.PROCESSING
        return self.session.task


class Storage:
    def __init__(
        self,
        events: list[str],
        value: bytes = b"hello world",
        *,
        fail_delete: bool = False,
    ) -> None:
        self.events = events
        self.value = value
        self.gets: list[str] = []
        self.puts: list[tuple[str, bytes, str]] = []
        self.deletes: list[str] = []
        self.fail_delete = fail_delete

    async def get(self, key: str) -> bytes:
        self.gets.append(key)
        self.events.append("storage.get")
        return self.value

    async def put(self, key: str, value: bytes, content_type: str) -> None:
        self.puts.append((key, value, content_type))
        self.events.append("storage.put")

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
        self.events.append("storage.delete")
        if self.fail_delete:
            raise RuntimeError("parsed cleanup failed")


class Index:
    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail
        self.calls: list[tuple[Any, ...]] = []

    async def replace_document(self, *args: Any) -> None:
        self.events.append("index")
        if self.fail:
            raise RuntimeError("index failed")
        self.calls.append(args)


class Embedder:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def embed(self, text: str) -> list[float]:
        self.events.append("embed")
        return [float(len(text))]


class AsyncEmbedder:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.events.append("embed_batch")
        return [[float(len(text))] for text in texts]


def make_entities() -> tuple[uuid.UUID, uuid.UUID, Any, Any]:
    tid, did, kb_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    task: Any = Obj()
    document: Any = Obj()
    task.id, task.document_id, task.status = tid, did, TaskStatus.PENDING
    task.stage, task.progress, task.error = TaskStage.QUEUED, 0, None
    task.completed_at = None
    document.id, document.knowledge_base_id, document.filename = did, kb_id, "a.txt"
    document.source_object_key, document.parsed_object_key = "kb/source/a.txt", None
    document.status, document.chunk_count, document.error = DocumentStatus.PENDING, 0, None
    return tid, did, task, document


@pytest.mark.asyncio
async def test_run_persists_exact_progress_payload_and_processing_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tid, did, task, document = make_entities()
    events: list[str] = []
    factory = Factory(task, document)
    storage = Storage(events)
    index = Index(events)
    original_chunk = ingestion_module.chunk_text

    def recording_chunk(text: str) -> Any:
        events.append("chunk")
        return original_chunk(text)

    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    monkeypatch.setattr(ingestion_module, "chunk_text", recording_chunk)
    await IngestionService(factory, storage, index, Embedder(events)).run(tid, did)

    progress = [(stage, value) for stage, value, _, _ in factory.commits]
    for expected in [
        (TaskStage.PARSING, 20),
        (TaskStage.CHUNKING, 40),
        (TaskStage.EMBEDDING, 60),
        (TaskStage.INDEXING, 80),
        (TaskStage.COMPLETED, 100),
    ]:
        assert expected in progress
    assert events == ["storage.get", "storage.put", "chunk", "embed", "index"]
    parsed_key, payload, content_type = storage.puts[0]
    assert parsed_key == "kb/parsed.json"
    assert json.loads(payload) == {"text": "hello world"}
    assert content_type == "application/json"
    assert index.calls[0][1] == did
    assert list(index.calls[0][2][0].vector) == [11.0]
    assert all(parsed is None for _, value, _, parsed in factory.commits if value < 100)
    assert document.parsed_object_key == parsed_key


@pytest.mark.asyncio
async def test_run_uses_async_embedding_client_for_batch_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tid, did, task, document = make_entities()
    events: list[str] = []
    factory = Factory(task, document)
    storage = Storage(events)
    index = Index(events)
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)

    await IngestionService(factory, storage, index, AsyncEmbedder(events)).run(tid, did)

    assert "embed_batch" in events
    assert "embed" not in events
    assert list(index.calls[0][2][0].vector) == [11.0]


@pytest.mark.asyncio
async def test_completed_task_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    tid, did, task, document = make_entities()
    task.status = TaskStatus.COMPLETED
    events: list[str] = []
    storage, index = Storage(events), Index(events)
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    await IngestionService(Factory(task, document), storage, index, Embedder(events)).run(tid, did)
    assert storage.gets == []
    assert index.calls == []


@pytest.mark.asyncio
async def test_failure_marks_entities_in_independent_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tid, did, task, document = make_entities()
    events: list[str] = []
    factory = Factory(task, document)
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    storage = Storage(events)
    with pytest.raises(RuntimeError, match="index failed"):
        await IngestionService(factory, storage, Index(events, fail=True)).run(tid, did)
    assert task.status == TaskStatus.FAILED
    assert document.status == DocumentStatus.FAILED
    assert task.error == document.error == "index failed"
    assert storage.deletes == ["kb/parsed.json"]
    assert factory.sessions[-1] is not factory.sessions[-2]


@pytest.mark.asyncio
async def test_compensation_commit_failure_is_explicit_with_processing_error_as_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tid, did, task, document = make_entities()
    events: list[str] = []
    factory = Factory(task, document, fail_compensation=True)
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    with pytest.raises(DocumentCleanupFailedError, match="failed status") as caught:
        await IngestionService(factory, Storage(events), Index(events, fail=True)).run(tid, did)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value.__cause__) == "index failed"
    assert factory.rollbacks == 1


@pytest.mark.asyncio
async def test_parsed_cleanup_failure_is_explicit_with_processing_error_as_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tid, did, task, document = make_entities()
    events: list[str] = []
    storage = Storage(events, fail_delete=True)
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)

    with pytest.raises(DocumentCleanupFailedError, match="parsed object") as caught:
        await IngestionService(Factory(task, document), storage, Index(events, fail=True)).run(
            tid, did
        )

    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value.__cause__) == "index failed"
    assert task.status == TaskStatus.FAILED
    assert document.status == DocumentStatus.FAILED
    assert storage.deletes == ["kb/parsed.json"]
