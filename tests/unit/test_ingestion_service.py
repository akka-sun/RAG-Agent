import uuid

import pytest

from app.models.document import DocumentStatus
from app.models.ingestion_task import TaskStage, TaskStatus
from app.services import ingestion as ingestion_module
from app.services.ingestion import IngestionService


class Obj:
    pass


class Session:
    def __init__(self, task, document):
        self.task, self.document = task, document
        self.commits = 0

    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    async def get(self, model, ident):
        name = getattr(model, "__name__", "")
        return self.task if name == "IngestionTask" else self.document
    async def commit(self): self.commits += 1
    async def rollback(self): pass


class Factory:
    def __init__(self, task, document): self.task, self.document = task, document; self.sessions = []
    def __call__(self):
        session = Session(self.task, self.document); self.sessions.append(session); return session


class Repo:
    def __init__(self, session): self.session = session
    async def get(self, _): return self.session.task
    async def claim_pending(self, _):
        if self.session.task.status != TaskStatus.PENDING: return None
        self.session.task.status = TaskStatus.PROCESSING; return self.session.task


class Storage:
    def __init__(self, value=b"hello world"): self.value, self.puts = value, []
    async def get(self, _): return self.value
    async def put(self, key, value, content_type): self.puts.append((key, value, content_type))


class Index:
    def __init__(self, fail=False): self.calls, self.fail = [], fail
    async def replace_document(self, *args):
        if self.fail: raise RuntimeError("index failed")
        self.calls.append(args)


class Embedder:
    def embed(self, text): return [float(len(text))]


def make_entities():
    tid, did, kb = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    task, doc = Obj(), Obj()
    task.id, task.document_id, task.status = tid, did, TaskStatus.PENDING
    task.stage, task.progress, task.error = TaskStage.QUEUED, 0, None
    task.completed_at = None
    doc.id, doc.knowledge_base_id, doc.filename = did, kb, "a.txt"
    doc.source_object_key, doc.parsed_object_key = "kb/source/a.txt", None
    doc.status, doc.chunk_count, doc.error = DocumentStatus.PENDING, 0, None
    return tid, did, task, doc


@pytest.mark.asyncio
async def test_run_progresses_all_stages_and_indexes(monkeypatch):
    tid, did, task, doc = make_entities(); factory = Factory(task, doc); storage, index = Storage(), Index()
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    service = IngestionService(factory, storage, index, Embedder())
    await service.run(tid, did)
    assert task.status == TaskStatus.COMPLETED and task.stage == TaskStage.COMPLETED and task.progress == 100
    assert doc.status == DocumentStatus.COMPLETED and doc.chunk_count > 0
    assert index.calls and storage.puts and len(factory.sessions) >= 8


@pytest.mark.asyncio
async def test_completed_task_is_idempotent(monkeypatch):
    tid, did, task, doc = make_entities(); task.status = TaskStatus.COMPLETED
    monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    index = Index(); await IngestionService(Factory(task, doc), Storage(), index, Embedder()).run(tid, did)
    assert not index.calls


@pytest.mark.asyncio
async def test_failure_marks_task_and_document_and_preserves_exception(monkeypatch):
    tid, did, task, doc = make_entities(); monkeypatch.setattr(ingestion_module, "IngestionTaskRepository", Repo)
    with pytest.raises(RuntimeError, match="index failed"):
        await IngestionService(Factory(task, doc), Storage(), Index(fail=True), Embedder()).run(tid, did)
    assert task.status == TaskStatus.FAILED and doc.status == DocumentStatus.FAILED
    assert task.error == doc.error == "index failed"
