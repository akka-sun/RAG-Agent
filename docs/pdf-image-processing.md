# PDF 图片处理

当前实现参考 Yuxi 的知识库解析链路：解析器负责把 PDF 转换为 Markdown，并返回 Markdown 引用的独立图片；系统将图片上传到 MinIO，再把 Markdown 中的本地图片路径替换为项目 API 地址。

```text
PDF
  -> MinerU ZIP(full.md + images/) 或 PaddleX markdown.text/images
  -> 图片写入 MinIO
  -> Markdown 图片链接改写为 /api/v1/.../images/{asset_index}
  -> ParsedDocument 分块
  -> 现有 Dense + BM25 + RRF + Reranker
```

## MinerU

Worker 调用 `/file_parse` 时启用 `return_md`、`response_format_zip` 和 `return_images`。ZIP 读取遵循以下规则：

- 优先读取 `full.md`，没有时读取第一个 Markdown 文件。
- 只接受安全的相对路径，并限制文件数量、解压后总大小和单张图片大小。
- 读取 `images/` 下的常见图片格式，图片二进制只在摄取期间保存在内存中。
- 如果 MinerU 返回旧版 JSON，继续使用现有结构化 block 兼容路径。

## PaddleX

Worker 从 `result.layoutParsingResults[*].markdown.text` 汇总 Markdown，并读取 `markdown.images` 中的 `图片路径 -> 图片 URL` 映射。图片下载后进入与 MinerU 相同的存储和链接改写流程；没有 Markdown 时继续使用 `prunedResult` block 兼容路径。

## 存储格式

`parsed.json` 新增：

- `markdown`：图片 URL 已改写的 Markdown。
- `assets`：图片序号、原路径、MIME、对象键、读取 URL、页码和解析器元数据。

图片二进制不会写入 `parsed.json`。图片对象键由知识库 ID、文档 ID 和资产序号生成，不使用解析器返回的路径作为存储路径。

图片读取接口：

```http
GET /api/v1/knowledge-bases/{knowledge_base_id}/documents/{document_id}/images/{asset_index}
```

接口只读取该文档 `parsed.json` 中登记的对象键。文档删除或摄取失败时，系统会同时清理已写入的图片对象。

## 检索行为

图片不建立独立向量，也不调用额外视觉模型生成描述。Markdown 中的标题、正文、图片 alt 文本和图片链接一起进入现有文本分块与索引链路，这与 Yuxi 的知识库 RAG 处理方式保持一致。
