# 循证引擎与安全边界

[← 返回项目首页](../README.md)

EviLife 将健康问题组织为可追溯的主张与证据。文本模型负责部分理解和表达，证据筛选、引用核验、安全 Gate 与主张级 Verdict 分别由管线中的规则和校验模块约束。

本文概述当前代码入口；更完整的设计与核查见 [引擎设计](./EVIDENCE_ENGINE_2_SPEC.md) 和 [审计记录](./EVIDENCE_ENGINE_2_AUDIT.md)。

## 1. 从问题到证据

```text
用户输入
  → 注入检测 / 安全路由 / 主题匹配
  → Fast / Deep 路径
  → FOR 与 AGAINST 独立查询
  → 相关性与方向校准 / 去重 / 分级 / RRF 融合
  → Evidence Mixer
  → Citation / Grounding 核验
  → Gate 与 Verdict
  → 模块卡片与 SSE 事件
```

编排入口：[orchestrator.py](../backend/app/orchestrator.py)。检索融合入口：[evidence_blend.py](../backend/app/evidence_blend.py)。

### 三类证据来源

| 来源 | 内容 | 代码或数据入口 |
| :--- | :--- | :--- |
| Evidence Packet | 预编译主题、支持主张、边界与可追溯来源 | [data/evidence/](../data/evidence/) · [repository.py](../backend/app/evidence/repository.py) |
| 权威语料库 | 审核主张、来源与分级文献记录 | [corpus.py](../backend/app/evidence/corpus.py) · [数据库结构](../data/authoritative_health/DATABASE_SCHEMA_V2.md) |
| Europe PMC | 网络检索的候选文献 | [evidence_blend.py](../backend/app/evidence_blend.py) · [europe_pmc.py](../backend/app/tools/europe_pmc.py) |

本地库可通过以下命令构建，在仓库根目录执行：

```bash
backend/.venv/bin/python data/authoritative_health/build_database.py
```

`EVILIFE_CORPUS_DB` 留空时自动发现仓库内数据库。设置该变量可指向其他兼容语料库。未配置模型密钥时，问答能力取决于预编译主题和离线语料的覆盖范围；不会因此获得任意主题的完整证据。

### 为什么分两个方向查询？

`EvidenceBlendService.build_bidirectional` 为两个方向使用独立查询，并在各自方向内进行 RRF（Reciprocal Rank Fusion）融合：

- **FOR**：Packet 支持主张、语料库支持材料、实时检索的支持候选。
- **AGAINST**：反对、冲突、混合结果和适用范围边界。

查询策略见 `TOPIC_DIRECTION_QUERIES`。候选材料还要通过主张相关性检查和方向校准，不能把检索命中直接当成有效支持或反对。

**边界不等于反证。** 某结论只适用于特定研究人群，这限制了外推范围，并不自动否定该人群中的结论。代码为 `support`、`against`、`mixed` 等方向保留区别，Verdict 分别计算直接反对与边界材料。

## 2. 排序、融合与引用

| 环节 | 作用 | 实现 |
| :--- | :--- | :--- |
| 主张准入 | 检查候选是否真正涉及当前问题 | [admission.py](../backend/app/evidence/admission.py) |
| 去重与排序 | 合并重复材料，按相关性、证据等级等信号排序 | [dedup.py](../backend/app/evidence/dedup.py) · [ranker.py](../backend/app/evidence/ranker.py) |
| RRF 融合 | 融合多个来源的排序结果 | [rrf.py](../backend/app/evidence/rrf.py) |
| Evidence Mixer | 将可靠证据权重和回答约束传入生成过程 | [evidence_blend.py](../backend/app/evidence_blend.py) |
| 引用核验 | 检查引用是否能对齐已有来源 | [citation_verifier.py](../backend/app/evidence/citation_verifier.py) |
| Grounding | 检查输出主张与证据的对应关系 | [grounding.py](../backend/app/evidence/grounding.py) |

系统通过可追溯标识和程序校验约束引用。引用存在、标识可核验与结论能否适用于具体人群是不同问题，阅读时仍应查看原文和局限。

## 3. Gate 与 Verdict 是两种判断

### Gate：回答可以怎样输出？

| 状态 | 含义 |
| :--- | :--- |
| `normal` | 在当前证据与安全范围内正常输出。 |
| `degraded` | 信息有限、边界触发或服务降级，限制结论并提示局限。 |
| `refused` | 命中诊断、停换药、药物剂量等受限请求，或其他安全拒绝条件。 |

规则入口：[safety.py](../backend/app/evidence/safety.py)。

### Verdict：主张得到怎样的证据支持？

`build_verdict` 根据支持数量、直接反对、边界、证据强度、冲突与主张类型计算结果。

| 结果 | 一般含义 |
| :--- | :--- |
| `true` · 是 | 在当前证据、问题范围和规则下获得足够支持。 |
| `partly_true` · 部分正确 | 支持有限、主张过宽，或存在冲突与外推边界。 |
| `false` · 否 | 直接反对证据占优，或无支持但存在足够反对材料。 |
| `insufficient` · 证据不足 | 当前信息不足以形成明确判定，或 Gate 已拒绝。 |

具体条件以 [verdict.py](../backend/app/evidence/verdict.py) 为准，上表不替代完整规则。输出还包含证据等级、支持与反对明细、适用与不适用人群、不确定性及更新时间。

`confidence` 是程序根据证据信号计算的规则分数，不应解释为经过临床校准的诊断概率。输出结构由 [verdict.schema.json](../contracts/verdict.schema.json) 约束，网页端使用 [VerdictCard.tsx](../components/evidence/VerdictCard.tsx) 渲染。

## 4. AI、视觉服务与降级

文本模型通过 OpenAI-compatible 接口接入，配置见 [backend/.env.example](../backend/.env.example) 和 [ai_provider.py](../backend/app/ai_provider.py)：

```dotenv
DEEPSEEK_API_KEY=
EVILIFE_AI_BASE_URL=https://api.deepseek.com
EVILIFE_AI_FAST_MODEL=deepseek-v4-flash
EVILIFE_AI_DEEP_MODEL=deepseek-v4-pro
```

以上模型名称来自仓库示例，部署时以供应商实际可用模型为准。也可通过 `EVILIFE_AI_API_KEY` 等兼容配置接入其他服务。

餐食和报告图片使用独立视觉服务：

```dotenv
EVILIFE_VISION_API_KEY=
EVILIFE_VISION_BASE_URL=
EVILIFE_AI_VISION_MODEL=deepseek-ai/deepseek-vl2-small
```

当前视觉调用依赖 `AIProvider.from_env` 初始化：还需启用 `EVILIFE_AI_ENABLED` 并提供文本模型密钥。填写文本密钥不会自动启用视觉识别。图片中的文字和指令按输入数据处理，餐食热量以区间和置信信息表达，结果需用户确认后再保存。

非健康问题走独立的受限通用问答，显示范围说明，不进入医疗 Evidence Flow，也不生成医疗引用。通用伦理边界由 `general_ethics_gate` 等规则约束。

## 5. 输入与输出防护

[guardrails.py](../backend/app/guardrails.py) 提供多层约束：

| 防护 | 行为 |
| :--- | :--- |
| 数据与指令分离 | 用户文本、文档和图片内容作为数据；使用包装标签和系统提示声明输入边界。 |
| 输入检测 | 检测直接注入、系统提示提取、越狱、伪授权、编码混淆等模式。 |
| 输出验证 | 检查系统提示泄露指纹和可疑注入跟随，触发时走失败或降级路径。 |
| 医疗安全路由 | 规则先检查个体诊断、停换药、剂量、紧急风险等请求。 |
| 下游证据约束 | 引用核验、Grounding、Gate 和 Verdict 进一步约束可呈现内容。 |

这些机制用于降低错误与注入风险，不保证覆盖所有变体。对应回归用例见 [test_guardrails.py](../backend/tests/test_guardrails.py)。

## 6. 响应与缓存

- FOR / AGAINST 实时查询通过并行调用减少串行等待。
- 同问题的 blend 缓存默认 TTL 为 300 秒；Europe PMC 查询缓存默认 TTL 为 600 秒。
- 网络客户端复用连接；摘要片段会限制长度，减少输入体积。
- 未启用实时检索时使用本地证据通道。外部服务不可用时，回答能力仍受剩余证据和降级策略限制。

缓存及并行逻辑见 [evidence_blend.py](../backend/app/evidence_blend.py)。上述为实现策略，实际响应时间取决于网络、模型和命中情况。

## 7. API 入口

接口定义见 [main.py](../backend/app/main.py)，启动后可在 `/docs` 查看交互式文档。

| 接口 | 用途 |
| :--- | :--- |
| `POST /api/v1/orchestrate` | 提交问题与附件，返回任务 ID 和模块计划。 |
| `GET /api/v1/runs/{run_id}/events` | SSE 任务事件流。 |
| `GET /api/v1/runs/{run_id}` | 查询任务状态。 |
| `POST /api/v1/reports/analyze` | 上传并分析体检报告。 |
| `GET /api/v1/reports` | 读取账号的报告历史。 |
| `GET /api/v1/health` | 后端状态检查。 |

真实账号、会话与个人记录由服务端运行库管理；证据库与运行库用途分离。部署与持久化要求见 [DEPLOYMENT.md](../DEPLOYMENT.md)。
