# 阶段 7：完整 PDF 解析实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持 PDF 上传并通过 Docker 中的 MinerU 或 PaddleX 真实解析服务生成统一 `ParsedDocument`，让 Markdown、TXT 和 PDF 共享同一结构化解析、分块、引用元数据和 MinIO 解析产物链路。

**Architecture:** 新增 `app/parsers` 模块定义 parser 协议、`ParsedDocument`、本地 Markdown/TXT 解析器、MinerU/PaddleX HTTP 适配器；上传 API 对 PDF 要求显式 parser 或使用配置默认值；Worker 调用 parser 后统一分块并写入 Milvus。

**Tech Stack:** FastAPI multipart, MinIO, ARQ Worker, Docker Compose MinerU, Docker Compose PaddleX, HTTP parser clients, Pydantic, pytest, Ruff, Pyright.

## Global Constraints

- MinerU runs as a real Docker Compose parser service.
- PaddleX runs as a real Docker Compose parser service.
- PDF upload must explicitly select MinerU or PaddleX, or use a documented default from configuration.
- No automatic parser fallback. The selected parser either succeeds or records its real failure.
- MinIO stores both the original file and the structured parsed artifact.
- Runtime code must never hard-code credentials.

---

## File Structure

- Modify `docker-compose.yml`: add `mineru` and `paddlex` services under the Compose profile `parser`.
- Modify `.env.example`: add parser base URLs and default PDF parser.
- Modify `app/core/config.py`: parser settings.
- Create `app/parsers/types.py`: `ParsedDocument`, `ParsedBlock`, `ParserName`.
- Create `app/parsers/local.py`: Markdown/TXT local parsers.
- Create `app/parsers/mineru.py`: MinerU client adapter.
- Create `app/parsers/paddlex.py`: PaddleX client adapter.
- Create `app/parsers/router.py`: parser selection and file-type validation.
- Modify `app/schemas/documents.py`: parser upload field.
- Modify `app/services/documents.py`: accept PDF and parser.
- Modify `app/services/ingestion.py`: use parser router and parsed blocks.
- Modify `app/rag/chunking.py`: chunk structured parsed blocks with citation metadata.
- Add unit, integration, and external parser tests.
- Update `README.md` and `docs/learning-roadmap.md`.

---

### Task 1: Parser Settings and Docker Services

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `app/core/config.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `mineru_base_url: str`, `paddlex_base_url: str`, `default_pdf_parser: Literal["mineru", "paddlex"]`.
- Consumes: existing settings model.

- [ ] **Step 1: Write failing settings test**

```python
def test_stage7_parser_settings(monkeypatch):
    monkeypatch.setenv("RAG_AGENT_MINERU_BASE_URL", "http://mineru:8000")
    monkeypatch.setenv("RAG_AGENT_PADDLEX_BASE_URL", "http://paddlex:8080")
    monkeypatch.setenv("RAG_AGENT_DEFAULT_PDF_PARSER", "mineru")

    settings = Settings()

    assert settings.mineru_base_url == "http://mineru:8000"
    assert settings.paddlex_base_url == "http://paddlex:8080"
    assert settings.default_pdf_parser == "mineru"
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_config.py::test_stage7_parser_settings -v`

Expected: FAIL because parser settings are missing.

- [ ] **Step 3: Add settings and Compose services**

Add parser settings. Add MinerU and PaddleX Docker services under the explicit Compose profile `parser`. Healthchecks must call `GET /health` for MinerU and `GET /health` for PaddleX through their internal service ports.

- [ ] **Step 4: Verify Compose**

Run:

```powershell
uv run --no-sync pytest tests/unit/test_config.py -v
docker compose config --quiet
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docker-compose.yml .env.example app/core/config.py tests/unit/test_config.py
git commit -m "feat: 配置 MinerU 与 PaddleX 解析服务"
```

---

### Task 2: ParsedDocument Types

**Files:**
- Create: `app/parsers/__init__.py`
- Create: `app/parsers/types.py`
- Test: `tests/unit/test_parser_types.py`

**Interfaces:**
- Produces: `ParserName`, `ParsedBlock`, `ParsedDocument`.
- Consumes: no infrastructure clients.

- [ ] **Step 1: Write failing type test**

```python
def test_parsed_document_preserves_page_and_heading_metadata():
    doc = ParsedDocument(
        parser="mineru",
        source_format="pdf",
        blocks=[
            ParsedBlock(text="Clause 1", page_number=3, heading_path=["Terms"], block_index=0),
        ],
    )

    assert doc.blocks[0].page_number == 3
    assert doc.blocks[0].heading_path == ["Terms"]
```

- [ ] **Step 2: Run failing test**

Run: `uv run --no-sync pytest tests/unit/test_parser_types.py -v`

Expected: FAIL because parser types are missing.

- [ ] **Step 3: Implement types**

Use Pydantic models or dataclasses with exact fields: parser, source format, metadata, ordered blocks, page number, heading path, block index, OCR confidence, coordinates, and parser version.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_parser_types.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/parsers/__init__.py app/parsers/types.py tests/unit/test_parser_types.py
git commit -m "feat: 定义统一 ParsedDocument 结构"
```

---

### Task 3: Local Markdown and TXT Parsers

**Files:**
- Create: `app/parsers/local.py`
- Test: `tests/unit/test_local_parsers.py`

**Interfaces:**
- Produces: `parse_markdown(filename: str, content: bytes) -> ParsedDocument`, `parse_txt(filename: str, content: bytes) -> ParsedDocument`.
- Consumes: `ParsedDocument` from Task 2.

- [ ] **Step 1: Write failing parser tests**

```python
def test_markdown_parser_extracts_heading_path():
    parsed = parse_markdown("guide.md", b"# Setup\n\nInstall Docker.\n\n## Run\n\nStart services.")

    assert parsed.source_format == "md"
    assert parsed.blocks[0].heading_path == ["Setup"]
    assert parsed.blocks[1].heading_path == ["Setup", "Run"]


def test_txt_parser_splits_paragraph_blocks():
    parsed = parse_txt("notes.txt", b"First paragraph.\n\nSecond paragraph.")

    assert [block.text for block in parsed.blocks] == ["First paragraph.", "Second paragraph."]
```

- [ ] **Step 2: Run failing tests**

Run: `uv run --no-sync pytest tests/unit/test_local_parsers.py -v`

Expected: FAIL because local parsers are missing.

- [ ] **Step 3: Implement local parsers**

Decode UTF-8, reject empty text, preserve block order, and include parser name `local`.

- [ ] **Step 4: Verify tests**

Run: `uv run --no-sync pytest tests/unit/test_local_parsers.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/parsers/local.py tests/unit/test_local_parsers.py
git commit -m "feat: 实现 Markdown 与 TXT 本地解析器"
```

---

### Task 4: MinerU and PaddleX Adapter Clients

**Files:**
- Create: `app/parsers/mineru.py`
- Create: `app/parsers/paddlex.py`
- Test: `tests/unit/test_parser_clients.py`
- Test: `tests/integration/test_parser_services_external.py`

**Interfaces:**
- Produces: `MinerUParser.parse_pdf(filename: str, content: bytes) -> ParsedDocument`, `PaddleXParser.parse_pdf(filename: str, content: bytes) -> ParsedDocument`.
- Consumes: parser service base URLs.

- [ ] **Step 1: Write failing HTTP adapter tests**

```python
async def test_mineru_parser_maps_blocks(respx_mock):
    respx_mock.post("http://mineru.test/parse").mock(
        return_value=httpx.Response(
            200,
            json={"blocks": [{"text": "PDF text", "page": 1, "type": "paragraph"}], "version": "x"},
        )
    )
    parser = MinerUParser(base_url="http://mineru.test")

    parsed = await parser.parse_pdf("doc.pdf", b"%PDF")

    assert parsed.parser == "mineru"
    assert parsed.blocks[0].page_number == 1
```

- [ ] **Step 2: Run failing tests**

Run: `uv run --no-sync pytest tests/unit/test_parser_clients.py -v`

Expected: FAIL because parser clients are missing.

- [ ] **Step 3: Implement clients**

Each client uploads the PDF bytes to its configured service, maps service output into `ParsedDocument`, and raises `ParserServiceError(parser, status_code, message)` on non-success.

- [ ] **Step 4: Add external Docker parser tests**

The parser integration test must skip unless parser services are running and `RAG_AGENT_EXTERNAL_TESTS_ENABLED=true`. It sends a small PDF fixture and asserts at least one text block.

- [ ] **Step 5: Verify unit tests**

Run: `uv run --no-sync pytest tests/unit/test_parser_clients.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/parsers/mineru.py app/parsers/paddlex.py tests/unit/test_parser_clients.py tests/integration/test_parser_services_external.py
git commit -m "feat: 接入 MinerU 与 PaddleX PDF 解析器"
```

---

### Task 5: Parser Router and Upload Contract

**Files:**
- Create: `app/parsers/router.py`
- Modify: `app/schemas/documents.py`
- Modify: `app/services/documents.py`
- Modify: `app/api/routes/documents.py`
- Test: `tests/unit/test_parser_router.py`
- Test: `tests/integration/test_documents_api.py`

**Interfaces:**
- Produces: `ParserRouter.select(filename: str, parser: str | None) -> DocumentParser`.
- Consumes: local and PDF parser adapters.

- [ ] **Step 1: Write failing router tests**

```python
def test_pdf_uses_explicit_parser():
    router = ParserRouter(
        default_pdf_parser="mineru", mineru=MinerUParserFake(), paddlex=PaddleXParserFake()
    )

    assert router.select("paper.pdf", parser="paddlex").name == "paddlex"


def test_markdown_rejects_external_parser():
    router = ParserRouter(default_pdf_parser="mineru")

    with pytest.raises(UnsupportedParserError):
        router.select("readme.md", parser="mineru")
```

- [ ] **Step 2: Run failing tests**

Run: `uv run --no-sync pytest tests/unit/test_parser_router.py -v`

Expected: FAIL because router is missing.

- [ ] **Step 3: Implement router and upload schema**

Allow `.md`, `.txt`, and `.pdf`. PDF parser values are `mineru` and `paddlex`. Markdown/TXT parser must be absent or `local`.

- [ ] **Step 4: Verify API upload contract**

Run: `uv run --no-sync pytest tests/integration/test_documents_api.py -v`

Expected: PASS, including 422 for unsupported parser combinations.

- [ ] **Step 5: Commit**

```powershell
git add app/parsers/router.py app/schemas/documents.py app/services/documents.py app/api/routes/documents.py tests/unit/test_parser_router.py tests/integration/test_documents_api.py
git commit -m "feat: 支持 PDF 上传解析器选择"
```

---

### Task 6: Worker ParsedDocument Ingestion and Structured Chunking

**Files:**
- Modify: `app/services/ingestion.py`
- Modify: `app/rag/chunking.py`
- Modify: `app/infrastructure/object_storage.py`
- Test: `tests/unit/test_chunking.py`
- Test: `tests/unit/test_ingestion_service.py`
- Test: `tests/e2e/test_async_ingestion.py`

**Interfaces:**
- Consumes: `ParsedDocument`.
- Produces: chunks with page, heading, block index, parser metadata for Milvus and citations.

- [ ] **Step 1: Write failing structured chunk test**

```python
def test_chunk_parsed_document_preserves_page_metadata():
    parsed = ParsedDocument(
        parser="mineru",
        source_format="pdf",
        blocks=[
            ParsedBlock(text="A long paragraph about retention.", page_number=2, block_index=0)
        ],
    )

    chunks = chunk_parsed_document(parsed, document_id=uuid.uuid4())

    assert chunks[0].metadata["page_number"] == 2
    assert chunks[0].metadata["parser"] == "mineru"
```

- [ ] **Step 2: Run failing tests**

Run: `uv run --no-sync pytest tests/unit/test_chunking.py tests/unit/test_ingestion_service.py -v`

Expected: FAIL because chunker and worker still use raw text.

- [ ] **Step 3: Implement parsed ingestion**

Worker reads source bytes, selects parser, stores structured parsed JSON in MinIO, chunks parsed blocks, embeds chunks, writes Milvus, and updates document parsed key.

- [ ] **Step 4: Verify E2E**

Run: `uv run --no-sync pytest tests/e2e/test_async_ingestion.py -v`

Expected: PASS for Markdown/TXT without parser services.

- [ ] **Step 5: Commit**

```powershell
git add app/services/ingestion.py app/rag/chunking.py app/infrastructure/object_storage.py tests/unit/test_chunking.py tests/unit/test_ingestion_service.py tests/e2e/test_async_ingestion.py
git commit -m "feat: 使用 ParsedDocument 统一摄取分块"
```

---

### Task 7: Stage 7 Documentation and Acceptance

**Files:**
- Modify: `README.md`
- Modify: `docs/learning-roadmap.md`
- Create: `docs/plans/2026-08-09-stage-7-progress.md`

**Interfaces:**
- Consumes: Tasks 1-6 verification outputs.
- Produces: documented PDF parser setup and acceptance.

- [ ] **Step 1: Update README**

Document PDF upload, parser selection, MinerU/PaddleX Docker startup, parsed artifact format, and no-fallback behavior.

- [ ] **Step 2: Update roadmap**

Add Stage 7 completion record and parser adapter review prompts.

- [ ] **Step 3: Run final gates**

Run:

```powershell
docker compose config --quiet
docker compose exec api uv run --no-sync ruff format --check .
docker compose exec api uv run --no-sync ruff check .
docker compose exec api uv run --no-sync pyright
docker compose exec api uv run --no-sync pytest tests/unit -v
docker compose exec api uv run --no-sync pytest tests/integration -v
docker compose exec api uv run --no-sync pytest tests/e2e -v
```

Expected: PASS. Parser external tests require parser containers and explicit external flag.

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/learning-roadmap.md docs/plans/2026-08-09-stage-7-progress.md
git commit -m "docs: 完成阶段七 PDF 解析验收记录"
```
