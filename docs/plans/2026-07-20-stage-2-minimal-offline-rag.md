# 阶段 2：最小离线 RAG 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可通过 HTTP 验证的最小离线 RAG 链路，将 Markdown/TXT 文本同步分块、生成确定性向量、写入按知识库隔离的进程内索引，并返回带稳定引用的本地回答。

**Architecture:** `app/rag` 保存无框架依赖的分块、Embedding、数据类型和进程内向量索引；`RAGService` 校验 PostgreSQL 知识库并编排摄取与查询；API 层只负责依赖注入和 Schema 转换。阶段 2 不调用真实模型、不保存原始文件，服务重启后索引明确丢失。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2.0 async、PostgreSQL 18、标准库 `hashlib`、pytest、pytest-asyncio、httpx、Ruff、Pyright、Docker Compose。

## Global Constraints

- 项目目录固定为 `RAG-Agent/`，不得导入其他项目的业务代码。
- Python 版本范围保持 `>=3.12,<3.14`。
- 所有开发、测试和检查命令在 Docker Compose 的 `api` 容器中运行。
- 代码标识符使用英文；文档、API 描述和测试数据可使用中文。
- 每个功能先观察目标测试因缺少行为而失败，再编写最小实现。
- 摄取接口只接受 JSON，不实现 multipart 上传或原始文件保存。
- 只接受 `.md` 和 `.txt` 文件名；空内容、空查询和 Top-K 范围错误返回统一 422。
- 摄取和查询必须校验 `knowledge_base_id` 已存在，并沿用阶段 1 的统一 404。
- 分块固定默认 `chunk_size=500`、`overlap=100`；Embedding 固定 64 维并且跨进程确定。
- 索引只保存在当前 API 进程内，必须按知识库隔离；不得伪装成持久化或生产级向量存储。
- 不增加真实 LLM、Embedding API、Reranker、Document 数据库表、Redis、ARQ、MinIO、Milvus、BM25、RRF、PDF 或异步任务。
- 不预设插件注册系统、通用向量库接口或未来阶段暂时用不到的抽象。

---

## 文件结构

阶段结束时新增或修改：

```text
RAG-Agent/
├── app/
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       └── rag.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── chunking.py
│   │   ├── embedding.py
│   │   ├── store.py
│   │   └── types.py
│   ├── schemas/
│   │   └── rag.py
│   ├── services/
│   │   └── rag.py
│   └── main.py
├── tests/
│   ├── integration/
│   │   ├── conftest.py
│   │   ├── test_knowledge_bases_api.py
│   │   └── test_rag_api.py
│   └── unit/
│       ├── test_chunking.py
│       ├── test_embedding.py
│       ├── test_rag_schemas.py
│       ├── test_rag_service.py
│       └── test_vector_store.py
├── README.md
└── docs/learning-roadmap.md
```

---

### Task 1: RAG 核心类型与确定性字符分块

**Files:**

- Create: `app/rag/__init__.py`
- Create: `app/rag/types.py`
- Create: `app/rag/chunking.py`
- Create: `tests/unit/test_chunking.py`

**Interfaces:**

- Produces: `TextChunk`、`IndexedChunk`、`SearchResult`。
- Produces: `chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[TextChunk]`。
- Consumes: 仅使用 Python 标准库。

- [ ] **Step 1: 编写字符窗口与 overlap 失败测试**

创建 `tests/unit/test_chunking.py`：

```python
import pytest

from app.rag.chunking import chunk_text


def test_chunk_text_uses_overlapping_character_windows() -> None:
    chunks = chunk_text("abcdefghij", chunk_size=4, overlap=1)

    assert [(chunk.text, chunk.start, chunk.end) for chunk in chunks] == [
        ("abcd", 0, 4),
        ("defg", 3, 7),
        ("ghij", 6, 10),
    ]
    assert [chunk.index for chunk in chunks] == [0, 1, 2]


def test_chunk_text_normalizes_line_endings_and_empty_input() -> None:
    chunks = chunk_text("  first\r\nsecond  ", chunk_size=20, overlap=2)

    assert [chunk.text for chunk in chunks] == ["first\nsecond"]
    assert chunk_text("  \r\n  ") == []


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (4, -1), (4, 4), (4, 5)],
)
def test_chunk_text_rejects_invalid_window_configuration(
    chunk_size: int,
    overlap: int,
) -> None:
    with pytest.raises(ValueError):
        chunk_text("content", chunk_size=chunk_size, overlap=overlap)
```

- [ ] **Step 2: 运行测试并确认模块缺失**

```bash
uv run --no-sync pytest tests/unit/test_chunking.py -v
```

Expected: collection ERROR，`app.rag.chunking` 尚不存在。

- [ ] **Step 3: 创建核心不可变数据类型**

创建空文件 `app/rag/__init__.py`，并创建 `app/rag/types.py`：

```python
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextChunk:
    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_id: str
    text: str
    start: int
    end: int
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk: IndexedChunk
    score: float
```

- [ ] **Step 4: 实现最小字符窗口分块**

创建 `app/rag/chunking.py`：

```python
from app.rag.types import TextChunk


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(
            TextChunk(
                index=len(chunks),
                text=normalized[start:end],
                start=start,
                end=end,
            )
        )
        if end == len(normalized):
            break
        start = end - overlap

    return chunks
```

- [ ] **Step 5: 运行测试和静态检查**

```bash
uv run --no-sync pytest tests/unit/test_chunking.py -v
uv run --no-sync ruff check app/rag tests/unit/test_chunking.py
uv run --no-sync pyright app/rag tests/unit/test_chunking.py
```

Expected: 分块测试全部通过，Ruff/Pyright 通过。

- [ ] **Step 6: 提交**

```bash
git add app/rag tests/unit/test_chunking.py
git commit -m "feat: 增加确定性文本分块"
```

---

### Task 2: 确定性 Hashing Embedding

**Files:**

- Create: `app/rag/embedding.py`
- Create: `tests/unit/test_embedding.py`

**Interfaces:**

- Produces: `HashingEmbedder(dimensions: int = 64)`。
- Produces: `HashingEmbedder.embed(text: str) -> tuple[float, ...]`。
- Consumes: 英文/数字词元和单个 CJK 字符，不访问模型或网络。

- [ ] **Step 1: 编写确定性、归一化与 CJK 词元测试**

创建 `tests/unit/test_embedding.py`：

```python
import math

import pytest

from app.rag.embedding import HashingEmbedder


def test_hashing_embedder_is_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder(dimensions=64)

    first = embedder.embed("Python async database")
    second = embedder.embed("Python async database")

    assert first == second
    assert len(first) == 64
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)


def test_hashing_embedder_supports_cjk_and_empty_text() -> None:
    embedder = HashingEmbedder(dimensions=64)

    assert embedder.embed("数据库") != (0.0,) * 64
    assert embedder.embed("   ") == (0.0,) * 64


def test_hashing_embedder_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValueError):
        HashingEmbedder(dimensions=0)
```

- [ ] **Step 2: 运行测试并确认模块缺失**

```bash
uv run --no-sync pytest tests/unit/test_embedding.py -v
```

Expected: collection ERROR，`app.rag.embedding` 尚不存在。

- [ ] **Step 3: 实现确定性 Hashing Embedding**

创建 `app/rag/embedding.py`：

```python
import hashlib
import math
import re

TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u3400-\u4dbf\u4e00-\u9fff]")


class HashingEmbedder:
    def __init__(self, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        values = [0.0] * self.dimensions
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 == 0 else -1.0
            values[index] += sign

        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            return tuple(values)
        return tuple(value / norm for value in values)
```

- [ ] **Step 4: 运行测试和静态检查**

```bash
uv run --no-sync pytest tests/unit/test_embedding.py -v
uv run --no-sync ruff check app/rag/embedding.py tests/unit/test_embedding.py
uv run --no-sync pyright app/rag/embedding.py tests/unit/test_embedding.py
```

Expected: 3 个测试通过，Ruff/Pyright 通过。

- [ ] **Step 5: 提交**

```bash
git add app/rag/embedding.py tests/unit/test_embedding.py
git commit -m "feat: 增加确定性文本向量"
```

---

### Task 3: 按知识库隔离的进程内向量索引

**Files:**

- Create: `app/rag/store.py`
- Create: `tests/unit/test_vector_store.py`

**Interfaces:**

- Consumes: `IndexedChunk` 与已归一化查询向量。
- Produces: `InMemoryVectorStore.add(chunks: list[IndexedChunk]) -> None`。
- Produces: `InMemoryVectorStore.search(knowledge_base_id: uuid.UUID, query_vector: tuple[float, ...], top_k: int) -> list[SearchResult]`。

- [ ] **Step 1: 编写排序、过滤与知识库隔离测试**

创建 `tests/unit/test_vector_store.py`：

```python
import uuid

from app.rag.store import InMemoryVectorStore
from app.rag.types import IndexedChunk


def make_chunk(
    knowledge_base_id: uuid.UUID,
    chunk_id: str,
    vector: tuple[float, ...],
) -> IndexedChunk:
    return IndexedChunk(
        knowledge_base_id=knowledge_base_id,
        document_id=uuid.uuid4(),
        filename="notes.txt",
        chunk_id=chunk_id,
        text=chunk_id,
        start=0,
        end=len(chunk_id),
        vector=vector,
    )


def test_store_ranks_positive_scores_and_applies_top_k() -> None:
    knowledge_base_id = uuid.uuid4()
    store = InMemoryVectorStore()
    store.add(
        [
            make_chunk(knowledge_base_id, "second", (0.6, 0.8)),
            make_chunk(knowledge_base_id, "first", (1.0, 0.0)),
            make_chunk(knowledge_base_id, "filtered", (-1.0, 0.0)),
        ]
    )

    results = store.search(knowledge_base_id, (1.0, 0.0), top_k=2)

    assert [result.chunk.chunk_id for result in results] == ["first", "second"]
    assert [result.score for result in results] == [1.0, 0.6]


def test_store_isolates_knowledge_bases() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    store = InMemoryVectorStore()
    store.add([make_chunk(first_id, "first", (1.0, 0.0))])

    assert store.search(second_id, (1.0, 0.0), top_k=3) == []
```

- [ ] **Step 2: 运行测试并确认模块缺失**

```bash
uv run --no-sync pytest tests/unit/test_vector_store.py -v
```

Expected: collection ERROR，`app.rag.store` 尚不存在。

- [ ] **Step 3: 实现最小进程内索引**

创建 `app/rag/store.py`：

```python
import uuid

from app.rag.types import IndexedChunk, SearchResult


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, list[IndexedChunk]] = {}

    def add(self, chunks: list[IndexedChunk]) -> None:
        for chunk in chunks:
            self._items.setdefault(chunk.knowledge_base_id, []).append(chunk)

    def search(
        self,
        knowledge_base_id: uuid.UUID,
        query_vector: tuple[float, ...],
        top_k: int,
    ) -> list[SearchResult]:
        results = [
            SearchResult(
                chunk=chunk,
                score=sum(
                    query_value * chunk_value
                    for query_value, chunk_value in zip(
                        query_vector,
                        chunk.vector,
                        strict=True,
                    )
                ),
            )
            for chunk in self._items.get(knowledge_base_id, [])
        ]
        positive_results = [result for result in results if result.score > 0.0]
        positive_results.sort(key=lambda result: (-result.score, result.chunk.chunk_id))
        return positive_results[:top_k]
```

- [ ] **Step 4: 运行测试和静态检查**

```bash
uv run --no-sync pytest tests/unit/test_vector_store.py -v
uv run --no-sync ruff check app/rag/store.py tests/unit/test_vector_store.py
uv run --no-sync pyright app/rag/store.py tests/unit/test_vector_store.py
```

Expected: 2 个测试通过，Ruff/Pyright 通过。

- [ ] **Step 5: 提交**

```bash
git add app/rag/store.py tests/unit/test_vector_store.py
git commit -m "feat: 增加进程内向量索引"
```

---

### Task 4: RAG API 输入输出契约

**Files:**

- Create: `app/schemas/rag.py`
- Create: `tests/unit/test_rag_schemas.py`

**Interfaces:**

- Produces: `RAGDocumentCreate`、`RAGDocumentResponse`、`RAGQueryRequest`、`RAGSourceResponse`、`RAGQueryResponse`。
- Consumes: Pydantic 2 字段和模型校验器。

- [ ] **Step 1: 编写文件类型、空白和 Top-K 校验测试**

创建 `tests/unit/test_rag_schemas.py`：

```python
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.rag import RAGDocumentCreate, RAGQueryRequest


def test_document_create_accepts_markdown_and_strips_filename() -> None:
    data = RAGDocumentCreate(
        knowledge_base_id=uuid.uuid4(),
        filename=" notes.MD ",
        content="knowledge",
    )

    assert data.filename == "notes.MD"


@pytest.mark.parametrize("filename", ["notes.pdf", "notes", "   "])
def test_document_create_rejects_unsupported_filename(filename: str) -> None:
    with pytest.raises(ValidationError):
        RAGDocumentCreate(
            knowledge_base_id=uuid.uuid4(),
            filename=filename,
            content="knowledge",
        )


def test_document_create_rejects_blank_content() -> None:
    with pytest.raises(ValidationError):
        RAGDocumentCreate(
            knowledge_base_id=uuid.uuid4(),
            filename="notes.txt",
            content="   ",
        )


@pytest.mark.parametrize("top_k", [0, 11])
def test_query_rejects_top_k_outside_supported_range(top_k: int) -> None:
    with pytest.raises(ValidationError):
        RAGQueryRequest(
            knowledge_base_id=uuid.uuid4(),
            query="database",
            top_k=top_k,
        )
```

- [ ] **Step 2: 运行测试并确认 Schema 缺失**

```bash
uv run --no-sync pytest tests/unit/test_rag_schemas.py -v
```

Expected: collection ERROR，`app.schemas.rag` 尚不存在。

- [ ] **Step 3: 实现完整请求与响应 Schema**

创建 `app/schemas/rag.py`：

```python
import uuid
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator


class RAGDocumentCreate(BaseModel):
    knowledge_base_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        filename = value.strip()
        if Path(filename).suffix.lower() not in {".md", ".txt"}:
            raise ValueError("filename must use .md or .txt")
        return filename

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if not self.content.strip():
            raise ValueError("content must not be blank")
        return self


class RAGDocumentResponse(BaseModel):
    document_id: uuid.UUID
    chunk_count: int


class RAGQueryRequest(BaseModel):
    knowledge_base_id: uuid.UUID
    query: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("query must not be blank")
        return query


class RAGSourceResponse(BaseModel):
    label: str
    document_id: uuid.UUID
    filename: str
    chunk_id: str
    text: str
    start: int
    end: int
    score: float


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[RAGSourceResponse]
```

- [ ] **Step 4: 运行测试和静态检查**

```bash
uv run --no-sync pytest tests/unit/test_rag_schemas.py -v
uv run --no-sync ruff check app/schemas/rag.py tests/unit/test_rag_schemas.py
uv run --no-sync pyright app/schemas/rag.py tests/unit/test_rag_schemas.py
```

Expected: Schema 测试全部通过，Ruff/Pyright 通过。

- [ ] **Step 5: 提交**

```bash
git add app/schemas/rag.py tests/unit/test_rag_schemas.py
git commit -m "feat: 增加最小 RAG 接口契约"
```

---

### Task 5: 摄取、检索与引用回答 Service

**Files:**

- Create: `app/services/rag.py`
- Create: `tests/unit/test_rag_service.py`

**Interfaces:**

- Consumes: `KnowledgeBaseService.get()`、`chunk_text()`、`HashingEmbedder`、`InMemoryVectorStore` 和 RAG Schema。
- Produces: `RAGService.ingest(data: RAGDocumentCreate) -> RAGDocumentResponse`。
- Produces: `RAGService.query(data: RAGQueryRequest) -> RAGQueryResponse`。

- [ ] **Step 1: 编写摄取、查询、引用和无证据失败测试**

创建 `tests/unit/test_rag_service.py`：

```python
import uuid
from unittest.mock import AsyncMock

import pytest

from app.rag.embedding import HashingEmbedder
from app.rag.store import InMemoryVectorStore
from app.schemas.rag import RAGDocumentCreate, RAGQueryRequest
from app.services.knowledge_base import KnowledgeBaseService
from app.services.rag import RAGService


@pytest.mark.asyncio
async def test_service_ingests_and_queries_with_stable_citations() -> None:
    knowledge_base_id = uuid.uuid4()
    knowledge_base_service = AsyncMock(spec=KnowledgeBaseService)
    service = RAGService(
        knowledge_base_service=knowledge_base_service,
        store=InMemoryVectorStore(),
        embedder=HashingEmbedder(),
        chunk_size=50,
        overlap=10,
    )

    document = await service.ingest(
        RAGDocumentCreate(
            knowledge_base_id=knowledge_base_id,
            filename="notes.md",
            content="Python async applications use an event loop. PostgreSQL stores records.",
        )
    )
    response = await service.query(
        RAGQueryRequest(
            knowledge_base_id=knowledge_base_id,
            query="Python async",
            top_k=2,
        )
    )

    assert document.chunk_count == 2
    assert response.sources
    assert response.sources[0].label == "S1"
    assert response.sources[0].document_id == document.document_id
    assert "[S1]" in response.answer
    assert knowledge_base_service.get.await_count == 2


@pytest.mark.asyncio
async def test_service_returns_empty_result_without_indexed_evidence() -> None:
    knowledge_base_service = AsyncMock(spec=KnowledgeBaseService)
    service = RAGService(
        knowledge_base_service=knowledge_base_service,
        store=InMemoryVectorStore(),
        embedder=HashingEmbedder(),
    )

    response = await service.query(
        RAGQueryRequest(
            knowledge_base_id=uuid.uuid4(),
            query="missing",
        )
    )

    assert response.answer == "未找到相关证据。"
    assert response.sources == []
```

- [ ] **Step 2: 运行测试并确认 Service 缺失**

```bash
uv run --no-sync pytest tests/unit/test_rag_service.py -v
```

Expected: collection ERROR，`app.services.rag` 尚不存在。

- [ ] **Step 3: 实现 RAG Service**

创建 `app/services/rag.py`：

```python
import uuid

from app.rag.chunking import chunk_text
from app.rag.embedding import HashingEmbedder
from app.rag.store import InMemoryVectorStore
from app.rag.types import IndexedChunk
from app.schemas.rag import (
    RAGDocumentCreate,
    RAGDocumentResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSourceResponse,
)
from app.services.knowledge_base import KnowledgeBaseService


class RAGService:
    def __init__(
        self,
        knowledge_base_service: KnowledgeBaseService,
        store: InMemoryVectorStore,
        embedder: HashingEmbedder,
        chunk_size: int = 500,
        overlap: int = 100,
    ) -> None:
        self._knowledge_base_service = knowledge_base_service
        self._store = store
        self._embedder = embedder
        self._chunk_size = chunk_size
        self._overlap = overlap

    async def ingest(self, data: RAGDocumentCreate) -> RAGDocumentResponse:
        await self._knowledge_base_service.get(data.knowledge_base_id)
        document_id = uuid.uuid4()
        chunks = chunk_text(
            data.content,
            chunk_size=self._chunk_size,
            overlap=self._overlap,
        )
        self._store.add(
            [
                IndexedChunk(
                    knowledge_base_id=data.knowledge_base_id,
                    document_id=document_id,
                    filename=data.filename,
                    chunk_id=f"{document_id}:{chunk.index}",
                    text=chunk.text,
                    start=chunk.start,
                    end=chunk.end,
                    vector=self._embedder.embed(chunk.text),
                )
                for chunk in chunks
            ]
        )
        return RAGDocumentResponse(
            document_id=document_id,
            chunk_count=len(chunks),
        )

    async def query(self, data: RAGQueryRequest) -> RAGQueryResponse:
        await self._knowledge_base_service.get(data.knowledge_base_id)
        results = self._store.search(
            data.knowledge_base_id,
            self._embedder.embed(data.query),
            data.top_k,
        )
        if not results:
            return RAGQueryResponse(
                answer="未找到相关证据。",
                sources=[],
            )

        sources = [
            RAGSourceResponse(
                label=f"S{index}",
                document_id=result.chunk.document_id,
                filename=result.chunk.filename,
                chunk_id=result.chunk.chunk_id,
                text=result.chunk.text,
                start=result.chunk.start,
                end=result.chunk.end,
                score=result.score,
            )
            for index, result in enumerate(results, start=1)
        ]
        answer_lines = [
            "根据检索到的资料：",
            *[f"[{source.label}] {source.text}" for source in sources],
        ]
        return RAGQueryResponse(
            answer="\n".join(answer_lines),
            sources=sources,
        )
```

- [ ] **Step 4: 运行 Service 测试和核心回归**

```bash
uv run --no-sync pytest tests/unit/test_rag_service.py -v
uv run --no-sync pytest tests/unit/test_chunking.py tests/unit/test_embedding.py tests/unit/test_vector_store.py -v
uv run --no-sync ruff check app/rag app/services/rag.py tests/unit
uv run --no-sync pyright
```

Expected: 新增测试和核心回归全部通过，Ruff/Pyright 通过。

- [ ] **Step 5: 提交**

```bash
git add app/services/rag.py tests/unit/test_rag_service.py
git commit -m "feat: 增加最小 RAG 业务服务"
```

---

### Task 6: RAG 依赖注入与 HTTP API

**Files:**

- Modify: `app/api/dependencies.py`
- Create: `app/api/routes/rag.py`
- Modify: `app/main.py`
- Modify: `tests/integration/conftest.py`
- Modify: `tests/integration/test_knowledge_bases_api.py`
- Create: `tests/integration/test_rag_api.py`

**Interfaces:**

- Produces: `get_rag_store() -> InMemoryVectorStore` 进程内单例依赖。
- Produces: `get_rag_service(...) -> RAGService`。
- Produces: `POST /api/v1/rag/documents` 和 `POST /api/v1/rag/query`。
- Consumes: 阶段 1 的知识库 CRUD、统一 404/422 和测试数据库 Session 覆盖。

- [ ] **Step 1: 将共享 API Client 夹具移入 integration conftest**

将 `tests/integration/conftest.py` 扩展为：

```python
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import get_session
from app.main import create_app


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    test_engine = create_async_engine(get_settings().test_database_url)
    test_session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
    )

    try:
        async with test_session_factory() as session:
            await session.execute(text("TRUNCATE TABLE knowledge_bases"))
            await session.commit()

            yield session

            await session.rollback()
            await session.execute(text("TRUNCATE TABLE knowledge_bases"))
            await session.commit()
    finally:
        await test_engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
```

从 `tests/integration/test_knowledge_bases_api.py` 删除本地 `client` fixture，并将导入收敛为：

```python
import pytest
from httpx import AsyncClient
```

其余三个知识库 API 测试保持不变。

- [ ] **Step 2: 编写 RAG API 失败测试**

创建 `tests/integration/test_rag_api.py`：

```python
import uuid

import pytest
from httpx import AsyncClient


async def create_knowledge_base(client: AsyncClient, name: str) -> str:
    response = await client.post(
        "/api/v1/knowledge-bases",
        json={
            "name": name,
            "description": "",
            "embedding_model": "hashing-64",
            "embedding_dimension": 64,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.integration
async def test_rag_ingest_and_query_returns_citations(client: AsyncClient) -> None:
    knowledge_base_id = await create_knowledge_base(client, "RAG API")
    ingest_response = await client.post(
        "/api/v1/rag/documents",
        json={
            "knowledge_base_id": knowledge_base_id,
            "filename": "notes.md",
            "content": "Python async applications use an event loop. PostgreSQL stores records.",
        },
    )

    assert ingest_response.status_code == 201
    document = ingest_response.json()
    assert document["chunk_count"] == 1

    query_response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": knowledge_base_id,
            "query": "Python async",
            "top_k": 3,
        },
    )

    assert query_response.status_code == 200
    result = query_response.json()
    assert "[S1]" in result["answer"]
    assert result["sources"][0]["label"] == "S1"
    assert result["sources"][0]["document_id"] == document["document_id"]


@pytest.mark.integration
async def test_rag_isolates_knowledge_bases(client: AsyncClient) -> None:
    first_id = await create_knowledge_base(client, "First RAG")
    second_id = await create_knowledge_base(client, "Second RAG")
    assert (
        await client.post(
            "/api/v1/rag/documents",
            json={
                "knowledge_base_id": first_id,
                "filename": "private.txt",
                "content": "private evidence",
            },
        )
    ).status_code == 201

    response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": second_id,
            "query": "private evidence",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "未找到相关证据。",
        "sources": [],
    }


@pytest.mark.integration
async def test_rag_rejects_missing_knowledge_base_and_invalid_file(
    client: AsyncClient,
) -> None:
    missing_response = await client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": str(uuid.uuid4()),
            "query": "anything",
        },
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "knowledge_base_not_found"

    knowledge_base_id = await create_knowledge_base(client, "Validation RAG")
    invalid_response = await client.post(
        "/api/v1/rag/documents",
        json={
            "knowledge_base_id": knowledge_base_id,
            "filename": "notes.pdf",
            "content": "content",
        },
    )
    assert invalid_response.status_code == 422
    assert invalid_response.json()["error"]["code"] == "validation_error"
```

- [ ] **Step 3: 运行测试并确认路由返回 404**

```bash
uv run --no-sync pytest tests/integration/test_rag_api.py -v
```

Expected: RAG 请求断言 FAIL，接口返回 404。

- [ ] **Step 4: 扩展依赖注入**

在 `app/api/dependencies.py` 增加导入：

```python
from functools import lru_cache

from app.rag.embedding import HashingEmbedder
from app.rag.store import InMemoryVectorStore
from app.services.rag import RAGService
```

在文件末尾增加：

```python
@lru_cache
def get_rag_store() -> InMemoryVectorStore:
    return InMemoryVectorStore()


@lru_cache
def get_hashing_embedder() -> HashingEmbedder:
    return HashingEmbedder(dimensions=64)


RAGStoreDependency = Annotated[InMemoryVectorStore, Depends(get_rag_store)]
HashingEmbedderDependency = Annotated[
    HashingEmbedder,
    Depends(get_hashing_embedder),
]


def get_rag_service(
    knowledge_base_service: KnowledgeBaseServiceDependency,
    store: RAGStoreDependency,
    embedder: HashingEmbedderDependency,
) -> RAGService:
    return RAGService(
        knowledge_base_service=knowledge_base_service,
        store=store,
        embedder=embedder,
    )


RAGServiceDependency = Annotated[RAGService, Depends(get_rag_service)]
```

依赖存在后，在 `tests/integration/conftest.py` 增加导入：

```python
from app.api.dependencies import get_rag_store
from app.rag.store import InMemoryVectorStore
```

并在 `client` fixture 中为每个测试创建和覆盖 Store：

```python
app = create_app()
rag_store = InMemoryVectorStore()


async def override_session() -> AsyncIterator[AsyncSession]:
    yield db_session


def override_rag_store() -> InMemoryVectorStore:
    return rag_store


app.dependency_overrides[get_session] = override_session
app.dependency_overrides[get_rag_store] = override_rag_store
```

- [ ] **Step 5: 创建薄 RAG Route**

创建 `app/api/routes/rag.py`：

```python
from fastapi import APIRouter, status

from app.api.dependencies import RAGServiceDependency
from app.schemas.errors import ErrorResponse
from app.schemas.rag import (
    RAGDocumentCreate,
    RAGDocumentResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post(
    "/documents",
    response_model=RAGDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def ingest_document(
    data: RAGDocumentCreate,
    service: RAGServiceDependency,
) -> RAGDocumentResponse:
    return await service.ingest(data)


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def query_rag(
    data: RAGQueryRequest,
    service: RAGServiceDependency,
) -> RAGQueryResponse:
    return await service.query(data)
```

- [ ] **Step 6: 在应用工厂注册 RAG Router**

在 `app/main.py` 增加导入：

```python
from app.api.routes.rag import router as rag_router
```

在现有知识库 Router 注册之后增加：

```python
router.include_router(knowledge_bases_router)
router.include_router(rag_router)
```

确保 `application.include_router(router)` 仍只调用一次。

- [ ] **Step 7: 运行 API 测试和阶段 1 回归**

```bash
uv run --no-sync pytest tests/integration/test_rag_api.py -v
uv run --no-sync pytest tests/integration/test_knowledge_bases_api.py -v
uv run --no-sync ruff format --check app tests
uv run --no-sync ruff check app tests
uv run --no-sync pyright
```

Expected: RAG API 3 个测试和知识库 API 3 个回归测试通过，格式、Ruff、Pyright 通过。

- [ ] **Step 8: 提交**

```bash
git add app/api app/main.py tests/integration
git commit -m "feat: 增加最小 RAG HTTP 接口"
```

---

### Task 7: 阶段 2 完整验收与学习记录

**Files:**

- Modify: `README.md`
- Modify: `docs/learning-roadmap.md`

**Interfaces:**

- Consumes: Task 1～6 的分块、Embedding、进程内索引、RAG Service 与 HTTP API。
- Produces: 可从干净环境复现的阶段 2 命令、真实 HTTP 证据和真实学习记录。

- [ ] **Step 1: 运行完整质量门槛**

```bash
uv run --no-sync ruff format --check app tests
uv run --no-sync ruff check app tests
uv run --no-sync pyright
uv run --no-sync pytest tests/unit -v
uv run --no-sync pytest tests/integration -v
```

Expected: format、Ruff、Pyright、全部单元与集成测试通过。

- [ ] **Step 2: 使用真实 HTTP 完成最小 RAG 验收**

在宿主机 PowerShell 创建知识库：

```powershell
$knowledgeBase = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/knowledge-bases `
  -ContentType application/json `
  -Body (@{
    name = "阶段二验收知识库"
    description = "最小离线 RAG"
    embedding_model = "hashing-64"
    embedding_dimension = 64
  } | ConvertTo-Json)
```

摄取 Markdown 文本：

```powershell
$document = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/rag/documents `
  -ContentType application/json `
  -Body (@{
    knowledge_base_id = $knowledgeBase.id
    filename = "stage-2.md"
    content = "Python 异步应用使用事件循环。PostgreSQL 用于保存业务记录。"
  } | ConvertTo-Json)
```

查询并检查引用：

```powershell
$result = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/rag/query `
  -ContentType application/json `
  -Body (@{
    knowledge_base_id = $knowledgeBase.id
    query = "Python 异步"
    top_k = 3
  } | ConvertTo-Json)

$result.answer
$result.sources
```

Expected: 回答包含 `[S1]`，`sources[0].document_id` 等于 `$document.document_id`。

清理验收知识库：

```powershell
Invoke-RestMethod -Method Delete `
  -Uri "http://127.0.0.1:8000/api/v1/knowledge-bases/$($knowledgeBase.id)"
```

- [ ] **Step 3: 更新 README**

在 `README.md` 增加：

```markdown
## 阶段 2 最小离线 RAG

- `POST /api/v1/rag/documents`：同步摄取 Markdown/TXT JSON 文本。
- `POST /api/v1/rag/query`：使用确定性 Hashing Embedding 检索并返回本地引用回答。

阶段 2 的索引只保存在 API 进程内，服务重启后丢失；它用于学习分块、向量检索和引用数据流，不代表生产级存储或语义模型质量。
```

- [ ] **Step 4: 完成口述验收**

不看文档回答：

1. 摄取链路从 HTTP JSON 到进程内索引经过哪些对象？
2. 查询链路如何从 query 得到 Top-K 与 `[S1]` 引用？
3. `chunk_size` 太大或太小分别有什么影响？
4. overlap 解决什么问题，又会带来什么代价？
5. 为什么归一化向量点积等于余弦相似度？
6. Hashing Embedding 为什么可确定测试，但不能代表真实语义模型质量？
7. “没有召回证据”和“回答没有使用证据”分别属于哪一段链路的问题？
8. 为什么不同知识库必须在检索前隔离，而不能召回后再过滤？
9. 为什么阶段 2 的进程内 Store 不能直接用于多进程或生产环境？

- [ ] **Step 5: 更新学习进度**

在 `docs/learning-roadmap.md` 的进度表追加实际完成记录。若在 2026-07-20 完成，格式为：

```markdown
| 2026-07-20 | 阶段 2 | Markdown/TXT 字符分块、确定性 Hashing Embedding、余弦检索、进程内知识库隔离、引用回答与最小 RAG API | 分块/Embedding/Store/Service 单元测试、真实 PostgreSQL API 集成测试、Ruff、Pyright、真实 HTTP 摄取与查询 | 以口述验收中能够独立解释的内容为准 | 以代码审查和口述验收中真实暴露的问题为准 |
```

如果实际完成日期不同，使用真实日期；“已掌握”和“待复习”不得直接复制示例，必须根据口述结果填写。

- [ ] **Step 6: 提交阶段文档**

```bash
git add README.md docs/learning-roadmap.md
git commit -m "docs: 完善阶段二最小 RAG 使用与学习记录"
```

## 阶段 2 完成定义

- [ ] `.md` 和 `.txt` JSON 文本可同步分块并索引，其他扩展名返回统一 422。
- [ ] 分块使用确定性 `500/100` 字符窗口，并保留 start/end 字符区间。
- [ ] Hashing Embedding 为固定 64 维、L2 归一化且跨进程确定。
- [ ] 余弦检索只返回正分候选，排序和 Top-K 截断可确定测试。
- [ ] 不同知识库的 chunks 在 Store 查询入口处隔离。
- [ ] 摄取和查询不存在知识库时返回统一 404。
- [ ] 查询返回带 `[S1]` 等稳定标签的回答和结构化 sources；无证据返回 200 与空 sources。
- [ ] 默认测试不依赖网络、付费模型、Redis、MinIO 或 Milvus。
- [ ] Ruff format、Ruff check、Pyright、单元和集成测试全部通过。
- [ ] 真实 HTTP 创建知识库、摄取、查询、引用核对和清理通过。
- [ ] README 说明进程内索引的丢失边界，学习进度按真实口述结果更新。

## 官方参考

- Python `hashlib`：<https://docs.python.org/3/library/hashlib.html>
- Python `dataclasses`：<https://docs.python.org/3/library/dataclasses.html>
- FastAPI Dependencies：<https://fastapi.tiangolo.com/tutorial/dependencies/>
- Pydantic Validators：<https://docs.pydantic.dev/latest/concepts/validators/>
- NumPy 余弦相似度说明不作为依赖；本阶段直接使用归一化向量点积。
