# RAG 评估说明

## 数据集格式

评估数据集支持 JSON 或 YAML：

```json
{
  "knowledge_base_id": "00000000-0000-0000-0000-000000000001",
  "questions": [
    {
      "id": "q1",
      "question": "What is the retention policy?",
      "expected_document_ids": ["00000000-0000-0000-0000-000000000002"],
      "expected_citations": [
        {
          "document_id": "00000000-0000-0000-0000-000000000002",
          "chunk_id": "0"
        }
      ],
      "tags": ["policy"]
    }
  ]
}
```

## 指标

- Recall@K：前 K 个结果覆盖预期文档的比例。
- MRR：第一个相关文档的倒数排名。
- Citation hit rate：返回引用命中预期 citation key 的比例。

## 运行方式

```powershell
docker compose exec api uv run --no-sync python scripts/run_evaluation.py `
  --dataset path/to/dataset.json `
  --output reports/rag-evaluation.md `
  --knowledge-base-id 00000000-0000-0000-0000-000000000001 `
  --limit 5
```

## 解读建议

- Dense 高、BM25 低：语义相近但关键词不稳定，适合继续优化 embedding 和 chunk。
- BM25 高、Dense 低：术语、编号、表格字段强，适合保留关键词召回。
- RRF 高于单路：混合检索带来互补收益。
- Rerank 高于 RRF：重排模型能有效识别问题与证据相关性。
- 引用命中率低：需要检查 chunk 粒度、PDF 页码/章节元数据和 citation 组装。

