# HealthCare 数据库双人开发任务书

## 1. 任务目标

两名成员分别负责两个边界清晰的 SQLite 数据库：

- **1号：权威证据库 V2**——保存经过审核的医学来源、文献、证据段落与主张关系；数据库只读，并可由证据包从零重建。
- **2号：运行数据库 V1**——保存用户生活记录、Apple Health 每日聚合、体检报告、分析任务与结果；数据库可写，并通过迁移文件持续升级。
- **3号：数据库独立验收**——检查1号、2号的实际提交和合并候选，以可复现证据决定是否允许合并，不开发第三个数据库。
- **整合负责人**——冻结共同契约，合并两人的代码，连接 FastAPI、OpenEvidence、DeepSeek、OCR 与前端，完成迁移和全量测试。

当前项目没有 SQLAlchemy 或 Alembic 依赖，现有数据库代码也使用标准库 `sqlite3`。比赛版本统一采用：

```text
sqlite3 + SQL 迁移文件 + Repository 层 + Pydantic 契约
```

---

## 2. 两人共同遵守的规范

### 2.1 统一 ID

```text
subject_id     sub-xxxxxxxxxxxx
report_id      rpt-xxxxxxxxxxxx
run_id         run-xxxxxxxxxxxx
finding_id     finding-xxxxxxxxxxxx

document_id    pubmed:12345678
               europe_pmc:PMC123456
               guideline:nice-ng136

claim_id       claim-xxxxxxxxxxxx
span_id        span-xxxxxxxxxxxx
```

文献内容发生变化时，不改变 `document_id`，只更新：

```text
content_hash
document_version
retrieved_at
```

业务对象使用带前缀的 UUID；外部文献使用来源名称与外部标识组成稳定 ID。

### 2.2 时间格式

- 数据库存 UTC：`2026-08-27T08:30:00Z`
- 每日指标日期：`2026-08-27`
- 时区使用 IANA 名称：`Asia/Shanghai`
- 前端展示时再转换成本地时间

### 2.3 禁止跨数据库外键

运行库中的：

```text
finding_evidence_links.evidence_id
```

只是对权威库 `evidence_documents.document_id` 的逻辑引用。SQLite 不能跨两个数据库建立外键，最终由后端服务验证引用是否存在。

### 2.4 SQLite 连接配置

运行数据库的每个连接都要执行：

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
```

权威数据库在服务运行时必须只读打开：

```python
sqlite3.connect("file:/path/authoritative_health.sqlite3?mode=ro", uri=True)
```

### 2.5 数据最小化

- 不保存 Apple Watch 每一次心跳原始样本
- 只保存每日聚合健康指标
- 不在 SQLite 中保存体检报告图片或 PDF 的二进制内容
- 报告文件单独临时保存，数据库只保存路径、哈希与保留期限
- Demo 使用匿名 `subject_id`
- 不将姓名、身份证号、手机号等身份信息写入测试数据

### 2.6 JSON 与哈希

- JSON 使用 UTF-8 和稳定字段顺序序列化
- 内容哈希统一使用 SHA-256
- JSON 字段必须先经过 Pydantic 或 JSON Schema 校验
- 不得在数据库中写入未验证的任意模型输出

---

# 3. 1号任务：权威证据库 V2

## 3.1 分支与负责范围

建议分支：

```text
feature/evidence-db-v2
```

负责文件：

```text
data/authoritative_health/
backend/app/evidence/corpus.py
backend/tests/test_authoritative_db_v2.py
```

不得修改：

```text
backend/app/main.py
backend/app/schemas.py
backend/app/lifestyle.py
backend/app/db/
Next.js 前端
```

## 3.2 数据来源

数据库构建只能使用：

- 已提交的 Evidence Packet JSON
- 人工审核过的指南清单
- 已确认的 PMID、PMCID、DOI 与官方来源链接

数据库构建阶段禁止联网。不能为了填字段伪造摘要、PMID、DOI、证据等级或原文 Span。

## 3.3 数据库位置

```text
data/authoritative_health/authoritative_health.sqlite3
```

数据库是构建产物，不允许在运行时修改。

## 3.4 表结构

### `schema_meta`

| 字段 | 类型 | 用途 |
|---|---|---|
| `schema_version` | TEXT | 例如 `2.0.0` |
| `corpus_version` | TEXT | 本轮证据语料版本 |
| `built_at` | TEXT | UTC 构建时间 |
| `builder_version` | TEXT | 构建脚本版本 |
| `source_digest` | TEXT | 所有输入证据包的整体 SHA-256 |

### `sources`

| 字段 | 类型 | 用途 |
|---|---|---|
| `source_id` | TEXT PK | 来源 ID |
| `title` | TEXT | 来源名称 |
| `organization` | TEXT | 发布机构 |
| `source_type` | TEXT | PubMed、指南、官方机构等 |
| `base_url` | TEXT | 官方网址 |
| `access_policy` | TEXT | `open`、`metadata_only`、`licensed` |
| `review_status` | TEXT | 审核状态 |

### `evidence_documents`

| 字段 | 类型 | 用途 |
|---|---|---|
| `document_id` | TEXT PK | 稳定 Evidence ID |
| `source_id` | TEXT FK | 来源 |
| `external_id` | TEXT | PMID、PMCID 或指南编号 |
| `pmid` | TEXT NULL | PubMed ID |
| `doi` | TEXT NULL | DOI |
| `title` | TEXT | 文献标题 |
| `abstract` | TEXT NULL | 摘要 |
| `year` | INTEGER NULL | 发表年份 |
| `publication_types_json` | TEXT | 研究类型 JSON |
| `evidence_tier` | TEXT | 证据层级 |
| `landing_url` | TEXT | 官方落地页 |
| `content_hash` | TEXT | 内容 SHA-256 |
| `document_version` | TEXT | 文档版本 |
| `retrieved_at` | TEXT NULL | 获取时间 |
| `review_status` | TEXT | 审核状态 |

要求：

- 非空 PMID 建立唯一索引
- 非空 DOI 建立唯一索引
- 所有外部 URL 必须使用 HTTPS
- `content_hash` 不允许为空

### `topics`

```text
topic_id       TEXT PRIMARY KEY
title_zh       TEXT NOT NULL
title_en       TEXT
aliases_json   TEXT NOT NULL
status         TEXT NOT NULL
```

### `document_topics`

```text
document_id    TEXT NOT NULL
topic_id       TEXT NOT NULL
relevance      REAL

PRIMARY KEY(document_id, topic_id)
```

### `evidence_spans`

只保存允许被答案引用的精确证据段落：

```text
span_id        TEXT PRIMARY KEY
document_id    TEXT NOT NULL
locator        TEXT NOT NULL
quote_text     TEXT NOT NULL
char_start     INTEGER
char_end       INTEGER
content_hash   TEXT NOT NULL
review_status  TEXT NOT NULL
```

`locator` 示例：

```text
abstract
page:12
table:2
section:Results
```

如果证据包没有精确原文，就不生成 Span。禁止用 AI 概括文本冒充原文引用。

### `claims`

迁移当前生活版主张：

```text
claim_id                 TEXT PRIMARY KEY
topic_id                 TEXT NOT NULL
claim_text_zh            TEXT NOT NULL
direction                TEXT NOT NULL
population               TEXT
finding                  TEXT NOT NULL
limitations              TEXT
evidence_strength        TEXT
safe_actions_json        TEXT NOT NULL
does_not_support_json    TEXT NOT NULL
review_status            TEXT NOT NULL
consumer_ready           INTEGER NOT NULL
```

`direction`限定为：

```text
support
boundary
mixed
context
```

### `claim_evidence_links`

```text
claim_id       TEXT NOT NULL
document_id    TEXT NOT NULL
span_id        TEXT NULL
relation       TEXT NOT NULL
is_primary     INTEGER NOT NULL DEFAULT 0
note           TEXT

PRIMARY KEY(claim_id, document_id, span_id)
```

`span_id`允许为空，因为部分主张当前只能关联到文献，还没有审核过的精确原文段落。

`relation`限定为：

```text
supports
refutes
context
boundary
```

## 3.5 具体开发步骤

1. 新建 `data/authoritative_health/schema_v2.sql`。
2. 扩展现有 `build_database.py`，从证据包生成 V2 表结构。
3. 迁移当前10个来源、33条 Claim 和10篇文献。
4. 将旧 `literature_records` 转换为 `evidence_documents`。
5. 建立 Claim 与 Document 的真实关系。
6. 只有存在精确原文时才建立 Span。
7. 建立 PMID、DOI、topic、claim 和 link 索引。
8. 将新数据库构建到同目录的临时文件。
9. 运行完整性、外键和数据数量校验。
10. 校验通过后使用原子替换更新正式数据库。
11. 更新 `AuthoritativeCorpus`，让后端读取 V2 表。
12. 保留旧数据库备份，不直接删除唯一副本。

## 3.6 构建安全要求

构建过程应遵循：

```text
输入证据包
→ 校验 JSON/Pydantic Schema
→ 计算 source_digest
→ 创建临时 SQLite
→ 创建表和索引
→ 写入数据
→ integrity_check
→ foreign_key_check
→ 业务数量校验
→ 原子替换正式数据库
```

构建时必须执行：

```sql
PRAGMA integrity_check;
PRAGMA foreign_key_check;
```

## 3.7 Repository 接口

至少提供：

```python
get_claim(claim_id)
get_claims_by_topic(topic_id)
get_document(document_id)
get_documents_by_topic(topic_id)
get_span(span_id)
get_claim_evidence(claim_id)
verify_document_id(document_id)
```

Repository 返回 Pydantic 对象或稳定字典，不允许将 `sqlite3.Row` 直接暴露给 API 层。

## 3.8 必须执行的校验

- 来源数不少于10
- Claim数不少于33
-文献数不少于10
- PMID无重复
- DOI无重复
- 不存在孤立Claim链接
- 所有外部URL使用HTTPS
- 所有文献均有`content_hash`
- 没有从概括文本伪造的Span
- 删除数据库后能从证据包重新构建
- 后端使用只读模式打开成功

## 3.9 必须交付

```text
schema_v2.sql
build_database.py
authoritative_health.sqlite3
corpus_manifest.json
数据库字段说明.md
test_authoritative_db_v2.py
```

## 3.10 验收标准

- 数据库能够从空目录重建
- 构建过程不访问网络
- `PRAGMA integrity_check`返回`ok`
- `PRAGMA foreign_key_check`无结果
- 现有证据检索测试通过
- 原有33条生活版主张得到保留
- 同一输入重复构建得到一致的数据记录和哈希

---

# 4. 2号任务：运行数据库 V1

## 4.1 分支与负责范围

建议分支：

```text
feature/runtime-db-v1
```

负责文件：

```text
backend/app/db/
backend/app/lifestyle.py
backend/app/apple_health_import.py
backend/tests/test_runtime_*.py
backend/tests/test_lifestyle_sqlite.py
backend/tests/test_healthkit_upsert.py
```

不得修改：

```text
data/authoritative_health/
backend/app/evidence/corpus.py
backend/app/main.py
backend/app/schemas.py
Next.js 前端
```

## 4.2 任务背景

当前 `LifestyleStore` 使用进程内列表和可选 JSON 文件保存数据。2号需要将其迁移为 SQLite Repository，同时尽量保持现有方法签名，避免破坏 FastAPI 路由和现有测试。

## 4.3 目录结构

```text
backend/app/db/
├── __init__.py
├── connection.py
├── migrate.py
├── runtime_repository.py
└── migrations/
    ├── 001_runtime_core.sql
    ├── 002_lifestyle.sql
    ├── 003_healthkit.sql
    └── 004_reports_analysis.sql
```

数据库位置：

```text
data/runtime/runtime.sqlite3
```

测试时必须支持通过环境变量指定临时路径：

```text
EVILIFE_RUNTIME_DB=/tmp/test-runtime.sqlite3
```

## 4.4 迁移机制

建立迁移记录表：

```sql
CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
```

启动时按照文件名顺序执行未应用的迁移：

```text
001 → 002 → 003 → 004
```

要求：

- 每个迁移文件在单独事务中执行
- 失败后整体回滚
- 已执行迁移不重复运行
- 对迁移SQL计算SHA-256
- 已执行迁移的checksum不一致时立即报错
- 禁止静默修改已经发布的迁移文件

## 4.5 表结构

### `subjects`

```text
subject_id      TEXT PRIMARY KEY
display_name    TEXT
timezone        TEXT NOT NULL
created_at      TEXT NOT NULL
deleted_at      TEXT
```

比赛Demo默认使用：

```text
sub-demo
```

### `health_connections`

```text
connection_id          TEXT PRIMARY KEY
subject_id             TEXT NOT NULL
provider               TEXT NOT NULL
device_id_hash         TEXT
status                 TEXT NOT NULL
authorized_types_json  TEXT NOT NULL
connected_at           TEXT NOT NULL
last_sync_at           TEXT
```

`provider`第一版支持：

```text
apple_healthkit
apple_health_export
demo_replay
```

### `health_sync_runs`

```text
sync_run_id      TEXT PRIMARY KEY
connection_id    TEXT NOT NULL
window_start     TEXT NOT NULL
window_end       TEXT NOT NULL
status           TEXT NOT NULL
received_count   INTEGER NOT NULL DEFAULT 0
accepted_count   INTEGER NOT NULL DEFAULT 0
skipped_count    INTEGER NOT NULL DEFAULT 0
payload_hash     TEXT
started_at       TEXT NOT NULL
finished_at      TEXT
error_code       TEXT
error_message    TEXT
```

这张表记录同步审计信息，不保存完整原始 HealthKit Payload。

### `health_daily_metrics`

使用窄表，新增指标时不修改表结构：

```text
metric_id      TEXT PRIMARY KEY
subject_id     TEXT NOT NULL
metric_date    TEXT NOT NULL
metric_type    TEXT NOT NULL
value          REAL NOT NULL
unit           TEXT NOT NULL
source         TEXT NOT NULL
coverage       REAL
timezone       TEXT NOT NULL
sync_run_id    TEXT
metadata_json  TEXT NOT NULL
created_at     TEXT NOT NULL
updated_at     TEXT NOT NULL
```

唯一约束：

```sql
UNIQUE(subject_id, metric_date, metric_type, source)
```

重复同步必须使用 UPSERT，不得新增重复记录。

第一版指标：

```text
steps
distance_km
active_energy_kcal
exercise_minutes
resting_heart_rate
average_heart_rate
hrv_sdnn
sleep_minutes
workout_minutes
weight_kg
waist_cm
water_ml
```

### `fasts`

```text
fast_id       TEXT PRIMARY KEY
subject_id    TEXT NOT NULL
start_at      TEXT NOT NULL
end_at        TEXT
goal_hours    REAL NOT NULL
status        TEXT NOT NULL
created_at    TEXT NOT NULL
```

### `meals`

```text
meal_id          TEXT PRIMARY KEY
subject_id       TEXT NOT NULL
action_id        TEXT NOT NULL
calorie_low      INTEGER NOT NULL
calorie_high     INTEGER NOT NULL
calorie_center   INTEGER NOT NULL
status           TEXT NOT NULL
created_at       TEXT NOT NULL
```

### `meal_items`

```text
meal_item_id        TEXT PRIMARY KEY
meal_id             TEXT NOT NULL
name                TEXT NOT NULL
portion             TEXT NOT NULL
portion_grams_json  TEXT
calorie_low         INTEGER NOT NULL
calorie_high        INTEGER NOT NULL
calorie_center      INTEGER NOT NULL
confidence          TEXT
reference_basis     TEXT
uncertainty         TEXT
```

### `observations`

保留现有手工和设备生活记录：

```text
observation_id  TEXT PRIMARY KEY
subject_id      TEXT NOT NULL
kind            TEXT NOT NULL
value           REAL
note            TEXT
source          TEXT NOT NULL
observed_at     TEXT NOT NULL
connector_id    TEXT
external_id     TEXT
created_at      TEXT NOT NULL
```

去重约束：

```sql
UNIQUE(connector_id, external_id)
```

这可以保持当前 Apple Health XML 重复导入时不产生重复数据。

### `reports`

```text
report_id          TEXT PRIMARY KEY
subject_id         TEXT NOT NULL
original_filename  TEXT NOT NULL
mime_type          TEXT NOT NULL
file_size          INTEGER NOT NULL
file_sha256        TEXT NOT NULL
storage_path       TEXT
status             TEXT NOT NULL
uploaded_at        TEXT NOT NULL
retention_until    TEXT
deleted_at         TEXT
```

数据库不保存报告文件Blob。

### `lab_items`

```text
lab_item_id       TEXT PRIMARY KEY
report_id         TEXT NOT NULL
canonical_code    TEXT
original_name     TEXT NOT NULL
value_numeric     REAL
value_text        TEXT
unit              TEXT
reference_low     REAL
reference_high    REAL
reference_text    TEXT
flag              TEXT NOT NULL
ocr_confidence    REAL
page_number       INTEGER
bbox_json         TEXT
confirmed         INTEGER NOT NULL DEFAULT 0
created_at        TEXT NOT NULL
updated_at        TEXT NOT NULL
```

`flag`限定为：

```text
LOW
NORMAL
HIGH
UNKNOWN
```

### `analysis_runs`

Apple Watch、体检报告和问答统一记录：

```text
run_id           TEXT PRIMARY KEY
subject_id       TEXT NOT NULL
input_type       TEXT NOT NULL
input_id         TEXT
status           TEXT NOT NULL
decision         TEXT
model_provider   TEXT
model_name       TEXT
prompt_version   TEXT
corpus_version   TEXT
started_at       TEXT NOT NULL
finished_at      TEXT
error_code       TEXT
error_message    TEXT
trace_json       TEXT NOT NULL
```

`input_type`限定为：

```text
healthkit
lab_report
question
```

### `findings`

```text
finding_id       TEXT PRIMARY KEY
run_id           TEXT NOT NULL
finding_type     TEXT NOT NULL
title            TEXT NOT NULL
summary_zh       TEXT NOT NULL
severity         TEXT NOT NULL
evidence_status  TEXT NOT NULL
data_quality     TEXT NOT NULL
created_at       TEXT NOT NULL
```

### `finding_evidence_links`

```text
finding_id   TEXT NOT NULL
evidence_id  TEXT NOT NULL
span_id      TEXT
relation     TEXT NOT NULL

PRIMARY KEY(finding_id, evidence_id, span_id)
```

`evidence_id`指向1号数据库中的`document_id`，但不建立SQLite外键。

### `corrections`

记录用户修正OCR结果：

```text
correction_id   TEXT PRIMARY KEY
subject_id      TEXT NOT NULL
entity_type     TEXT NOT NULL
entity_id       TEXT NOT NULL
field_name      TEXT NOT NULL
old_value_json  TEXT
new_value_json  TEXT NOT NULL
corrected_at    TEXT NOT NULL
```

## 4.6 具体开发步骤

1. 建立连接工厂并统一执行PRAGMA。
2. 建立带checksum的迁移执行器。
3. 编写`001`到`004`四个SQL迁移。
4. 建立`RuntimeRepository`。
5. 首先迁移`LifestyleStore`现有方法。
6. 保持当前FastAPI接口和方法签名尽量不变。
7. 将Apple Health XML聚合结果写入SQLite。
8. 实现`health_daily_metrics`幂等UPSERT。
9. 增加报告、Lab Item和Analysis Run写入方法。
10. 编写旧JSON一次性导入器。
11. 所有批量写入必须使用事务。
12. 增加重启持久化、并发写入和幂等测试。

## 4.7 旧JSON迁移

当前`LifestyleStore`可能通过`EVILIFE_LIFESTYLE_STORE`保存JSON。

新增：

```python
import_lifestyle_json(path, runtime_repository)
```

迁移规则：

```text
active_fast    → fasts
fast_history   → fasts
meals          → meals + meal_items
observations   → observations
```

迁移成功后：

- 写入迁移记录
- 不删除原JSON
- 重复执行不产生重复数据
- 等最终整合验收后再人工归档原文件

## 4.8 Repository 接口

设备与报告：

```python
create_subject(...)
create_health_connection(...)
start_sync_run(...)
finish_sync_run(...)
upsert_daily_metrics(...)
get_daily_metrics(...)
create_report(...)
save_lab_items(...)
confirm_lab_items(...)
create_analysis_run(...)
finish_analysis_run(...)
save_findings(...)
link_finding_evidence(...)
record_correction(...)
```

生活版兼容接口：

```python
start_fast(...)
end_fast(...)
add_observation(...)
add_device_observations_bulk(...)
confirm_meal(...)
get_today_summary(...)
```

## 4.9 必须测试的场景

- 同一Apple Health数据同步两次，不增加重复行
- 同一报告文件哈希重复上传时能识别
- 一批100条指标写入中途失败时全部回滚
- 迁移执行两次不会重复建表或重复写数据
- 修改已执行迁移文件后checksum校验报错
- 当前JSON生活记录可以完整迁移
-删除Subject采用软删除
- 原始报告路径为空时不影响结构化分析
- Finding可以保存权威库中的逻辑Evidence ID
- 运行库重启后数据仍然存在
- 并发请求不会出现`database is locked`的无处理异常

## 4.10 必须交付

```text
connection.py
migrate.py
runtime_repository.py
001_runtime_core.sql
002_lifestyle.sql
003_healthkit.sql
004_reports_analysis.sql
import_lifestyle_json.py
runtime数据库字段说明.md
test_runtime_migrations.py
test_runtime_repository.py
test_lifestyle_sqlite.py
test_healthkit_upsert.py
```

## 4.11 验收标准

- 新数据库能够从空文件自动迁移到最新版本
- 重复运行迁移安全且无副作用
- 现有生活记录API行为不变
- Apple Health重复同步保持幂等
- 事务失败不会留下半批数据
- 原始报告不以Blob形式进入SQLite
- 所有动态写入均经过Repository

---

# 5. 文件边界与冲突管理

| 文件区域 | 负责人 |
|---|---|
| `data/authoritative_health/` | 1号 |
| `backend/app/evidence/corpus.py` | 1号 |
| `backend/app/db/` | 2号 |
| `backend/app/lifestyle.py` | 2号 |
| `backend/app/apple_health_import.py` | 2号 |
| `backend/app/main.py` | 两人都不修改，由整合负责人处理 |
| `backend/app/schemas.py` | 两人都不修改，由整合负责人处理 |
| `.env`和启动脚本 | 整合负责人 |
| Next.js前端 | 两人都不修改 |

如果需要新增共享字段：

1. 在任务分支中新建说明文档或Contract草案。
2. 不直接修改共享路由和共享Schema。
3. 由整合负责人统一更新Pydantic契约。

---

# 6. 3号：数据库独立验收

3号不开发第三个数据库，而是独立检查1号、2号的实际提交。

3号负责：

- 核对分支、提交SHA、修改范围和交接材料
- 在干净环境中验证权威证据库可重建、只读和可审计
- 验证运行库迁移、事务、持久化和Apple Health幂等
- 运行两人的专项测试及合并候选的后端完整测试
- 检查统一ID、UTC时间、JSON、SHA-256和跨库逻辑引用契约
- 按P0至P3记录可复现问题并给出是否允许合并的结论

3号默认只检查、补充验收测试和写报告，不替1号、2号修改业务实现。P0或P1问题必须退回对应负责人；缺少关键材料时标记`BLOCKED`，不能写成`PASS`。

3号详细流程见：

```text
team_handoff/database_tasks/PERSON_3_START_HERE.md
team_handoff/database_tasks/PERSON_3_AI_PROMPT.md
team_handoff/database_tasks/PERSON_3_REVIEW_CHECKLIST.md
team_handoff/database_tasks/PERSON_3_REVIEW_REPORT_TEMPLATE.md
```

---

# 7. 提交与交付格式

每个人提交时必须提供：

1. 功能分支名称。
2. 修改文件清单。
3. 数据库结构说明。
4. 从空目录构建或迁移数据库的命令。
5. 测试命令和测试结果。
6. 示例数据库或测试Fixture。
7. 已知限制。
8. 不包含密钥的环境变量示例。

不得提交：

- API Key
- Apple开发者证书
- 真实健康数据
- 未脱敏体检报告
- 本地绝对路径
- 临时数据库锁文件
- SQLite WAL/SHM文件

---

# 8. 测试命令

后端完整测试：

```bash
cd HealthCare/backend
../.venv/bin/python -m pytest
```

1号可在开发中先运行：

```bash
cd HealthCare/backend
../.venv/bin/python -m pytest tests/test_authoritative_db_v2.py tests/test_dynamic_evidence_engine.py
```

2号可在开发中先运行：

```bash
cd HealthCare/backend
../.venv/bin/python -m pytest \
  tests/test_runtime_migrations.py \
  tests/test_runtime_repository.py \
  tests/test_lifestyle_sqlite.py \
  tests/test_healthkit_upsert.py \
  tests/test_lifestyle_api.py \
  tests/test_apple_health_import.py
```

---

# 9. 最终整合顺序

整合负责人按以下顺序合并：

1. 冻结统一ID、时间与JSON契约。
2. 合并权威证据库V2。
3. 验证证据库可重建和只读查询。
4. 合并运行数据库V1。
5. 迁移Lifestyle JSON和Apple Health XML路径。
6. 增加FastAPI依赖注入。
7. 接入Apple Health同步、OCR和报告分析。
8. 接入OpenEvidence、DeepSeek和Citation Audit。
9. 验证运行库Evidence ID能在权威库中解析。
10. 运行全部现有测试和新增数据库测试。
11. 验证Next.js构建与完整Demo链路。

---

# 10. 最终职责概括

## 1号

负责“可审计、可重建、只读的医学知识”。

成功标准：

> 任何生活版或专业版医学主张，都能追溯到真实Document；有精确原文时还能追溯到Span。

## 2号

负责“可持续写入、可迁移、可去重的用户和设备数据”。

成功标准：

> Apple Health、体检报告、用户修正和分析结果能够稳定保存；重复同步不重复，失败事务不留下脏数据。

两个数据库不互相直接操作，通过统一的`document_id/evidence_id`和后端服务完成逻辑关联。
