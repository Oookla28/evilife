# 权威证据库 V2 字段说明

## 构建与运行边界

- 权威输入仅为 `data/evidence/*.json` 中已提交、已审核的 Evidence Packet。
- 构建完全离线；旧 SQLite 只用于核对 10 个来源、33 条 Claim、10 篇文献的基线数量，不作为内容输入。
- 构建器先写同目录临时库，依次执行 `PRAGMA integrity_check`、`PRAGMA foreign_key_check` 和业务校验，通过后才替换正式库。
- 运行时通过 SQLite URI `mode=ro` 打开，每个连接执行 `PRAGMA foreign_keys = ON`。
- 所有 JSON 使用 UTF-8、中文不转义、键排序和紧凑分隔符序列化；内容哈希统一为 SHA-256。

## 表与关系

### `schema_meta`

数据库只有一行构建元数据：

| 字段 | 说明 |
|---|---|
| `schema_version` | 数据库结构版本，V2 为 `2.0.0` |
| `corpus_version` | Evidence Packet 声明的语料版本；未声明时由 `source_digest` 派生 |
| `built_at` | UTC 构建时间 |
| `builder_version` | 构建器版本 |
| `source_digest` | 按文件名确定性排序后，对全部输入文件计算的整体 SHA-256 |

### `sources`

保存来源及发布机构元数据。`source_id` 是主键；`base_url` 必须是 HTTPS；`access_policy` 只能为 `open`、`metadata_only` 或 `licensed`。

### `evidence_documents`

保存稳定的文献对象：

- `document_id` 是稳定主键。优先使用已审核的显式 ID；否则只从真实 PMID、PMCID、DOI、Cochrane 编号派生。都不存在时使用 `curated:<source-id>`，明确表示内部审核 ID，不冒充外部编号。
- `pmid` 和 `doi` 分别通过部分唯一索引约束非空值唯一。
- `abstract` 只接收 Evidence Packet 中的真实字段，绝不从 Claim、finding 或关键词拼接。
- `evidence_tier` 未显式审核时写入 `ungraded`，不从文献类型推断证据等级。
- `content_hash` 对规范化后的文献内容计算；内容更新时保留 `document_id`，调整 `document_version` 和 `content_hash`。
- `landing_url` 必须是 HTTPS。

### `topics` 与 `document_topics`

`topics` 保存主题标题、别名和状态；`document_topics` 建立 Document 与 Topic 的多对多关系。`relevance` 可为空；非空时范围为 0 到 1。

### `evidence_spans`

只保存 Evidence Packet 明确提供的精确引用：

- `locator` 指向摘要、页码、表格或章节等可定位位置。
- `quote_text` 必须为非空原文；构建器不把摘要、主张或 AI 概括自动转换为 Span。
- 对 `locator=abstract` 且带字符偏移的记录，构建器验证 `abstract[char_start:char_end]` 与 `quote_text` 完全一致。
- 未显式提供 `span_id` 时，只根据 `document_id + locator + quote_text` 生成稳定 ID。

### `claims`

保存面向生活版的审核主张。`direction` 仅允许 `support`、`boundary`、`mixed`、`context`。`safe_actions_json` 和 `does_not_support_json` 在入库前验证为字符串数组。

### `claim_evidence_links`

连接 Claim、Document 和可选 Span：

- `span_id` 为空表示当前只有文献级追溯关系。
- `span_id` 非空时，复合外键保证 Span 与 Document 一致。
- `relation` 仅允许 `supports`、`refutes`、`context`、`boundary`。
- 部分唯一索引确保同一 Claim 与 Document 只有一条 `span_id IS NULL` 的文献级关系。

## Evidence Packet V2 可选字段

现有 Evidence Packet 的 `topic`、`safe_actions`、`evidence_strength`、`evidence_items`、`supports`、`does_not_support` 继续兼容。为提高 V2 可追溯性，可在每个 `evidence_item` 中增加：

```json
{
  "document_id": "pubmed:12345678",
  "external_id": "12345678",
  "pmid": "12345678",
  "doi": "10.1000/example",
  "abstract": "经人工核对的真实摘要",
  "publication_types": ["Systematic Review"],
  "evidence_tier": "T2_evidence_synthesis",
  "document_version": "1",
  "retrieved_at": "2026-08-27T08:30:00Z",
  "evidence_spans": [
    {
      "span_id": "span-example-01",
      "locator": "abstract",
      "quote_text": "经人工核对的精确原文",
      "char_start": 0,
      "char_end": 12,
      "claim_ids": ["C_EXAMPLE_S1"],
      "review_status": "human_quote_checked"
    }
  ]
}
```

PMID、DOI、摘要、证据等级或原文没有经过确认时应省略；构建器不会补造这些字段。

## Repository 接口

`AuthoritativeCorpus` 提供：

```python
get_claim(claim_id)
get_claims_by_topic(topic_id)
get_document(document_id)
get_documents_by_topic(topic_id)
get_span(span_id)
get_claim_evidence(claim_id)
verify_document_id(document_id)
```

返回值为普通字典或字典列表，JSON 数组会解码为 Python 列表，布尔字段会标准化；不会向上层暴露 `sqlite3.Row`。数据库缺失、Schema 不兼容或 SQL 查询失败分别抛出清晰的 Repository 异常。原有搜索接口仍在数据库缺失时返回空列表，以保持现有动态证据引擎的降级行为。

