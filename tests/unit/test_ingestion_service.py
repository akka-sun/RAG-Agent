import json
import uuid

import pytest

from app.models.document import DocumentStatus
from app.models.ingestion_task import TaskStage, TaskStatus
from app.services import ingestion as ingestion_module
from app.services.ingestion import IngestionService


class Obj:
    pass


class Session:
    def __init__(self, factory, task, document):
        self.factory = factory
        self.task = task
        self.document = document

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, model, _ident):
        return self.task if model.__name__ == "IngestionTask" else self.document

    async def commit(self):
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

    async def rollback(self):
        self.factory.rollbacks += 1


class Factory:
    def __init__(self, task, document, *, fail_compensation=False):
        self.task = task
        self.document = document
        self.fail_compensation = fail_compensation
        self.sessions = []
        self.commits = []
        self.rollbacks = 0

    def __call__(self):
        session = Session(self, self.task, self.document)
        self.sessions.append(session)
        return session


class Repo:
    def __init__(self, session):
        self.session = session

    async def get(self, _task_id):
        return self.session.task

    async def claim_pending(self, _task_id):
        if self.session.task.status != TaskStatus.PENDING:
            return None
        self.session.task.status = TaskStatus.PROCESSING
        return self.session.task


class Storage:
    def __init__(self, events, value=b"hello world"):
        self.events = events
        self.value = value
        self.gets = []
        self.puts = []

    async def get(self, key):
        self.gets.append(key)
        self.events.append("storage.get")
        return self.value

    async def put(self, key, value, content_type):
        self.puts.append((key, value, content_type))
        self.events.append("storage.put")


class Index:
    def __init__(self, events, *, fail=False):
        self.events = events
        self.fail = fail
        self.calls = []

    async def replace_document(self, *args):
        self.events.append("index")
        if self.fail:
            raise RuntimeError("index failed")
        self.calls.append(args)


class Embedder:
    def __init__(self, events):
        self.events = events

    def embed(self, text):
        self.events.append("embed")
        return [float(len(text))]


def make_entities():
    tid, did, kb_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    task, document = Obj(), Obj()
    task.id, task.document_id, task.status = tid, did, TaskStatus.PENDING
    task.stage, task.progress, task.error = TaskStage.QUEUED, 0, None
    task.completed_at = None
    document.id, document.knowledge_base_id, document.filename = did, kb_id, "a.txt"
    document.source_object_key, document.parsed_object_key = "kb/source/a.txt", None
    document.status, document.chunk_count, document.error = DocumentStatus.PENDING, 0, None
    return tid, did, task, document


@pytest.mark.asyncio
async def test_run_persists_exact_progress_payload_and_processing_order(monkeypatch):
    tid, did, task, document = make_entities()
    events = []
    factory = Factory(task, document)
    storage = Storage(events)
    index = Index(events)
    original_chunk = ingestion_module.chunk_text

    def recording_chunk(text):
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
    assert index.calls[0][2][0].vector == [11.0]
    assert all(parsed is None for _, value, _, parsed in factory.commits if value < 100)
    assert document.parsed_object_key == parsed_key


@pytest.mark.asyncio
async def test_completed_task_is_idempotent(monkeypatch):
    tid, did, task, document = make_entities()
    task.status = TaskStatus.COMPLETED
    events = []
    storage, index = Storage(events), Index(events)
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    await IngestionService(Factory(task, document), storage, index, Embedder(events)).run(tid, did)
    assert storage.gets == []
    assert index.calls == []


@pytest.mark.asyncio
async def test_failure_marks_entities_in_independent_session(monkeypatch):
    tid, did, task, document = make_entities()
    events = []
    factory = Factory(task, document)
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    with pytest.raises(RuntimeError, match="index failed"):
        await IngestionService(factory, Storage(events), Index(events, fail=True)).run(tid, did)
    assert task.status == TaskStatus.FAILED
    assert document.status == DocumentStatus.FAILED
    assert task.error == document.error == "index failed"
    assert factory.sessions[-1] is not factory.sessions[-2]


@pytest.mark.asyncio
async def test_compensation_commit_failure_preserves_processing_exception(monkeypatch):
    tid, did, task, document = make_entities()
    events = []
    factory = Factory(task, document, fail_compensation=True)
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    with pytest.raises(RuntimeError, match="index failed") as caught:
        await IngestionService(factory, Storage(events), Index(events, fail=True)).run(tid, did)
    assert str(caught.value) == "index failed"
    assert factory.rollbacks == 1
