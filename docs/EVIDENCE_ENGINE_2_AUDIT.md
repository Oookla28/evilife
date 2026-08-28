# 「是非题」Evidence Engine 2.0 — 现状审计报告

> 文档版本：v1.0
> 日期：2026-08-12
> 审计人：首席 AI 系统架构师（AI-assisted）
> 仓库：`Aprivity/HealthCare`（本地路径 `F:\刘子驿\002大学\4.线下\26暑线下\summer3\frontend`）
> 审计方式：全量只读代码审查 + 测试运行验证（154 backend tests / 15 frontend tests 全绿）

---

## 0. 审计结论摘要（TL;DR）

**这是一个已经走完「第一代静态循证引擎」并部分进入「第二代动态引擎」的项目，不是从零开始。**

前几轮迭代已经交付了规格书中相当一部分 P0 能力：

| 规格书要求 | 当前状态 | 差距 |
|---|---|---|
| FOR / AGAINST 双向独立检索 | ✅ 已实现（`EvidenceBlendService.build_bidirectional`，EuropePMC 双查询并行 + 语料库通道） | DeepPath 类本身仍是静态拆包（见 §3.3） |
| 混合检索（lexical + corpus） | 🟡 RRF 融合（`rrf.py`）+ FTS/SQLite 语料库 | 无 dense/embedding；无真正 reranker |
| Citation Integrity | ✅ `CitationVerifier`（id/source/url/精确数字） | 无 semantic entailment（见 §3.6） |
| Evidence Gate 三态 | ✅ `EvidenceGate` + `SafetyRouter` | 需扩展为规则优先的完整策略 |
| Verdict 协议 | ✅ `verdict.py`（true/partly_true/false/insufficient + confidence + 双向证据） | 枚举与规格书建议不同，缺 `what_could_change_this_verdict` |
| 安全防御 | ✅ `guardrails.py`（注入检测 7 类 + 伦理边界 + 输出验证） | 超出规格书基础要求 |
| Claim Decomposer | ❌ 缺失 | 一个输入 → 一个回答，不支持多 Claim |
| Evidence Note | 🟡 有 `VerdictEvidenceItem`（近似） | 无独立 Evidence Note 模型（supports/does_not_support/limitations 来自文献的结构化抽取） |
| Reranker | ❌ 只有 RRF rank fusion | 无相关性/质量/人群匹配综合排序 |
| Trace | ❌ 只有 `timing_ms` | 无逐步 trace 记录 |
| Eval Harness + Golden Set | ❌ 缺失 | 12 题测试集只存在于文档，无数据文件、无 runner |
| 动态检索（非硬编码） | ✅ EuropePMC 实时 + 本地语料库 | 无 provider 抽象层，单实现 |
| 前端动画语义化 | 🟡 已有 SSE 事件骨架 | `PRINT_MS=2400` 仍为纯定时（§3.9） |

**核心结论**：架构骨架（Safety → Evidence → Verification → Answer → Verdict）已经立住且有 154 个测试兜底。本次升级是「保留 → 抽象 → 扩展 → 测试 → 迁移」，不推倒重写。

---

## 1. 当前真实架构

```text
User Input (text / image / pdf)
    │
    ▼
FastAPI /api/v1/orchestrate  (main.py)
    │
    ▼
Orchestrator.run_async  (orchestrator.py)
    │
    ├── L2 Guardrails: InjectionDetector.scan()          ← 注入/越狱/伪授权（high/medium → injection_refusal）
    │
    ├── SafetyRouter.assess()                            ← 规则优先：停药/剂量/诊断/高风险/人群/证据边界/伪授权
    │
    ├── EvaluationModeRouter.select()                    ← general / rag / always_deep / eviroute_gate
    │
    ├── 分支：
    │   ├─ document → DocumentSummary (mock)
    │   ├─ image    → MealAnalyzer (vision model)
    │   ├─ record   → HealthRecordDraft (health_intent)
    │   ├─ feature  → ChatFeaturePanel / FastingTimer (feature_intent)
    │   ├─ refused  → SafetyCard（safety_refusal）
    │   ├─ general  → 评测模式骨架
    │   ├─ rag / fast_path → FastPath.run()  (evidence/fast_path.py)
    │   │        └─ TopicMatcher.match() → repository.get(topic)  ← 静态拆包
    │   └─ deep_path → DeepPath.run()     (evidence/deep_path.py)
    │            └─ TopicMatcher.match() → repository.get(topic)  ← 静态拆包
    │
    ├── 公共增强（orchestrator._enrich_packet_module / _unknown_module）
    │   └─ EvidenceBlendService.build_bidirectional()
    │        ├─ curated: golden Packet supports/does_not_support
    │        ├─ curated: AuthoritativeCorpus (SQLite bootstrap corpus or EVILIFE_CORPUS_DB)
    │        ├─ live:    EuropePMC FOR query  ┐ asyncio.gather 并行
    │        ├─ live:    EuropePMC AGAINST query ┘
    │        └─ RRF 融合 → EvidenceBlend（reliable_weight = α 策略）
    │   └─ build_verdict()  (evidence/verdict.py)
    │   └─ AI enrichment（可选）：answer_health_question → OutputValidator
    │   └─ TCM perspective（中医意图才调 AI，否则确定性 fallback）
    │
    ▼
OrchestrateResponse（module_plan + evidence_count + timing_ms）
    │
    ▼
SSE /runs/{id}/events  （回放式：run 完成后一次性生成事件序列）
    │
    ▼
前端 ModuleRenderer → EvidenceAnswer（含 VerdictCard / CoverFlow / 引用抽屉）
```

### 关键分层观察

- **检索真正发生的地方不在 DeepPath，而在 orchestrator 的 `_enrich_packet_module` / `_unknown_module`**。`DeepPath.run()` 内部仍是 `repository.get(topic)` 静态拆包（`deep_path.py:59-60`）。这是职责命名问题：DeepPath 名为"深度通路"，实际联网在旁路完成。
- **support_query / boundary_query 已真正执行**：DeepPath 生成 `EvidenceQuerySet`，orchestrator 把它传给 `build_bidirectional(support_query=..., boundary_query=...)`，作为 EuropePMC 方向查询词。但它们**没有参与静态拆包**，静态拆包仍来自 golden Packet 的 `supports` / `does_not_support` 字段。
- **三层防线已有**：L1 输入注入检测 → L2 规则安全路由 → L3 输出验证 + Citation Integrity + Gate + Verdict。

---

## 2. 当前已实现能力（逐项）

### 2.1 证据引擎
| 模块 | 文件 | 能力 |
|---|---|---|
| `SafetyRouter` | `evidence/safety.py` | 9 类安全规则（停药/剂量/诊断/高风险/人群/证据边界/伪授权/处方审核/第三方用药），rule-first，模型不可覆盖 |
| `TopicMatcher` | `evidence/topic_matcher.py` | 关键词规则匹配，2 个 golden topic，硬编码在 Python |
| `EvaluationModeRouter` | `evidence/modes.py` | 4 评测模式 + 复杂度正则路由（fast/deep） |
| `EvidencePacketRepository` | `evidence/repository.py` | 从 `data/evidence/*.json` 加载/校验/缓存 Packet，schema 严格（extra=forbid） |
| `FastPath` | `evidence/fast_path.py` | golden Packet → 模板结论 + 引用校验，确定性、快、便宜 |
| `DeepPath` | `evidence/deep_path.py` | 静态拆包 support/boundary + gate + verify（联网在 orchestrator 旁路） |
| `CitationVerifier` | `evidence/citation_verifier.py` | integrity 类校验：evidence_id 存在、source_id 匹配、URL 在包内、精确数字受支持 |
| `grounding.py` | `evidence/grounding.py` | envelope 校验：source 存在 + 在检索包内；`semantic_entailment_checked: False`（明确诚实标记） |
| `EvidenceGate` | `evidence/safety.py` | 三态：normal/degraded/refused |
| `corpus.py` | `evidence/corpus.py` | authoritative_health.sqlite3：从审核 Packet 可重复生成的离线语料库；支持外部扩展库、CJK 窗口检索与 topic 回退 |
| `evidence_blend.py` | `evidence_blend.py` | 双向独立检索 + RRF 融合 + α 权重策略（风险→0.88，普通→0.78）+ 三层缓存 + 并行 |
| `verdict.py` | `evidence/verdict.py` | 确定性 Verdict：true/partly_true/false/insufficient + confidence + evidence_grade + 双向证据 + uncertainty |
| `guardrails.py` | `guardrails.py` | 注入检测（direct/extraction/jailbreak/ethics_spoof/encoded/obfuscated）+ 输出验证 + system prompt 隔离 |

### 2.2 数据资产
| 资产 | 内容 |
|---|---|
| `data/evidence/sodium.json` | golden Packet：WHO 钠指南 + Cochrane 系统综述（2 条证据项） |
| `data/evidence/mediterranean.json` | golden Packet：PREDIMED + Cochrane（2 条证据项） |
| `data/authoritative_health/` | `build_database.py` 从审核 Packet 生成 bootstrap SQLite；可用 `EVILIFE_CORPUS_DB` 替换为更大策展库 |
| `contracts/*.json` | 4 份 schema：evidence-packet / module-plan / stream-events / verdict |

### 2.3 前端
- EvidenceAnswer（结论 + gate 徽章 + evidence_mix 条形图 + VerdictCard + CoverFlow + 引用抽屉 + 调试面板）
- 苹果式动效：Polaroid 出纸、CoverFlow、Passbook Shredder（iOS 6.1.4 逆向参数）
- ModuleRenderer（注册表渲染，未知模块不崩溃）
- MealAnalyzer / FastingTimer / DocumentSummary / HealthProfile 等模块

### 2.4 工程
- 154 backend tests（19 文件）/ 15 frontend tests（7 文件）/ Playwright e2e
- 契约测试（jsonschema）
- TypeScript 编译 + `next build` 通过
- `.env.example` 完整（含 VISION_MODEL）

---

## 3. 当前 Demo / Mock / Hardcode 清单（规格书 §三 逐项对照）

| 检查点 | 现状 | 证据 |
|---|---|---|
| **TopicMatcher 关键词硬编码** | ⚠️ 是，2 个主题写死在 Python `_RULES` | `topic_matcher.py:8-19` |
| **Golden Packet 数量** | ⚠️ 仅 2 个（钠、地中海），16:8/咖啡/鸡蛋等主题无 Packet | `data/evidence/` 只有 2 个 json |
| **DeepPath 是否真正联网** | 🟡 半：`DeepPath.run()` 不联网（静态拆包）；联网在 orchestrator 旁路 `build_bidirectional` | `deep_path.py:59-60` vs `orchestrator.py:_enrich_packet_module` |
| **support_query 是否真正执行** | ✅ 真正执行（作为 EuropePMC FOR 查询词） | `orchestrator.py` 传 `queries.support_query` 给 blend |
| **boundary_query 是否真正执行** | ✅ 真正执行（EuropePMC AGAINST 查询词含 null/limitation 词） | `evidence_blend.py:TOPIC_DIRECTION_QUERIES` |
| **CitationVerifier 实际验证什么** | integrity：evidence_id 存在 / source_id 匹配 / URL 在包内 / 精确数字受支持；**无语义验证** | `citation_verifier.py` |
| **是否存在 semantic entailment 验证** | ❌ 无。`grounding.py` 明确 `semantic_entailment_checked: False` | `grounding.py` 末尾 |
| **是否存在真实 reranker** | ❌ 无。只有 RRF rank fusion（`rrf.py`），无相关性/质量/人群匹配综合评分 | `rrf.py` |
| **是否存在动态 retrieval** | ✅ EuropePMC 实时 + 语料库动态检索 | `evidence_blend.py` |
| **是否存在 Golden Set** | ❌ 无数据文件；12 题测试集只写在旧规划文档里 | `data/questions/` 不存在 |
| **是否存在 trace** | ❌ 无 trace 模块，只有 `timing_ms` 4 个时间戳 | `schemas.py:OrchestrateResponse.timing_ms` |
| **是否存在 evaluation harness** | ❌ 无 `eval/` 目录、无 runner | 顶层无 eval/ |
| **Claim Decomposer** | ❌ 无。输入→单一回答 | orchestrator 无 claims 概念 |
| **Evidence Note** | 🟡 `VerdictEvidenceItem` 近似（evidence_id/source_id/title/finding/url/direction/channel） | `schemas.py` |
| **用户 PDF 解析** | ⚠️ Mock：`DocumentSummary` 返回占位文本，不解析 PDF | `orchestrator.py:has_document` 分支 |
| **SSE 流式** | ⚠️ 回放式：orchestrate 完成后再生成事件序列，非实时流 | `main.py:run_events` |
| **前端 PRINT_MS** | ⚠️ 纯定时 2400ms，非事件驱动 | `app/lab/page.tsx:39` |
| **医学结论补全** | ✅ 正确拒绝：无来源时 `evidence_strength=insufficient` + 拒答，不补常识 | `ai_provider.py:answer_health_question` 无来源分支 |

---

## 4. 技术债（P0 → P3）

### P0 — 架构正确性（必须先修）
1. **Claim Decomposer 缺失**：多主张输入只能得到单一回答；规格书核心定位"替每个健康说法找证据"无法满足。
2. **Semantic Claim-Evidence Verifier 缺失**：目前文献说"无显著差异"，模型若引用它说"明显更优"，URL 校验会通过（integrity OK）但语义是错的。这是证据可信度的最大漏洞。
3. **Reranker 缺失**：RRF 只是融合，不解决"相关 vs 优质 vs 适用"排序。
4. **DeepPath 职责错位**：名为深度通路，实际静态拆包；需改造成"真正动态证据通路"，把 orchestrator 旁路的检索逻辑归位。
5. **Eval Harness + Golden Set 缺失**：无法回答"这个系统到底行不行"，也无法做 A/B/C 对比。

### P1 — 工程质量
6. **TopicMatcher 硬编码** → `TopicRegistry`（data 驱动，如 `data/topics/*.yaml`）。
7. **EvidenceProvider 抽象层缺失**：`EuropePMCSearch` 单实现，无法插拔 NCBI/ClinicalTrials/Mock。
8. **Verdict 协议待扩展**：现有 4 值枚举 vs 规格书 6 值建议；缺 `what_could_change_this_verdict`。
9. **Evidence Grade 无理由**：只有 `high/medium/low/insufficient` 枚举，无 strengths/limitations 理由。
10. **Applicability 分析缺失**：只有 target/non_target_population 字符串列表，无 DIRECT/PARTIAL/UNCERTAIN/NOT_APPLICABLE 判定。
11. **Conflict Detection 简单化**：`conflict_detected` 是 bool，无人群/干预/结局/时间尺度/质量维度分析。
12. **缓存无过期元数据**：blend 缓存有 TTL，但无 `retrieved_at/expires_at/source_updated_at` 落库；证据新鲜度不可审计。
13. **SSE 非真流式** + **PRINT_MS 纯定时**：需事件驱动出纸（`max(min_print, evidence_ready)`）。
14. **Trace 缺失**：无法向用户/审计方展示"为什么这么判断"的完整证据链。

### P2 — 能力增强
15. **Query Expansion 缺失**：单查询无同义词/临床变体/边界查询扩展（需 `MAX_QUERY_EXPANSION` 上限）。
16. **Agent 异常处理**：无"最新证据缺失/只见旧指南/FOR 多 AGAINST 0/人群不匹配"的异常分支（限 3 轮）。
17. **用户 PDF → Evidence Note**：当前 mock，需真实解析 + 与外部证据对比。
18. **Source Policy 分层**：无权威指南>系统综述>RCT>观察性>网页的显式策略（reliability_score 已有雏形）。
19. **Badcase Registry**：无 `eval/badcases.jsonl` 回归机制。

### P3 — 远期
20. **向量检索 / embedding**：当前 lexical/FTS 足够第一阶段，可后加。
21. **MCP 适配**：规格书明确"Python Tool → 稳定接口 → Adapter → MCP（可选）"，暂不强制。
22. **LangGraph 等编排框架**：规格书明确先 Python Workflow，FSM 可维护则不引入。

---

## 5. 与规格书 52 条要求的符合度矩阵

| 规格书章节 | 状态 | 说明 |
|---|---|---|
| §一 禁止重写 | ✅ | 本审计即"保留→抽象→扩展"的基础 |
| §三 先 Audit | ✅ | 本文档 |
| §五 Claim Decomposer | ❌ | P0-1 |
| §六 Evidence Tool Layer | 🟡 | 有 EuropePMCSearch 单实现，无 Provider 抽象 |
| §七 开源基础设施调研 | 🟡 | 已用 Europe PMC；NCBI/ClinicalTrials/BioMCP 未接 |
| §九 FOR/AGAINST | ✅ | 已实现（并行 + 记录） |
| §十 Query Expansion | ❌ | P2-15 |
| §十一 Hybrid Retrieval | 🟡 | lexical + corpus，无 dense |
| §十二 Reranker | ❌ | P0-3 |
| §十三 Evidence Note | 🟡 | VerdictEvidenceItem 近似 |
| §十四 CitationVerifier 改名 | 🟡 | 需 `CitationIntegrityVerifier` 别名 + 新 `ClaimEvidenceVerifier` |
| §十五 Semantic Verifier | ❌ | P0-2 |
| §十六 Evidence Grade | 🟡 | 有枚举无理由 |
| §十七 Applicability | ❌ | P1-10 |
| §十八 Conflict Detection | 🟡 | bool 级 |
| §十九 Verdict Protocol | 🟡 | v1 已实现，待对齐 |
| §二十 Evidence Gate | ✅ | 三态 + 拒答不补全 |
| §二十一 Evidence Mixer | ✅ | reliable_weight 策略已实现（prompt 权重控制） |
| §二十二/二十三 Agent 限制 | ❌ | P2-16 |
| §二十四 Trace | ❌ | P1-14 |
| §二十五 Trace→前端动画 | ❌ | P1-13 |
| §二十六/二十七 Eval + Golden Set | ❌ | P0-5（本次建立数据集） |
| §二十八 指标 | ❌ | 随 eval 一起 |
| §二十九 A/B/C | ❌ | 随 eval 一起 |
| §三十 Badcase Registry | ❌ | P2-19 |
| §三十一 FastPath 保留 | ✅ | 保留中 |
| §三十二 DeepPath 动态化 | ❌ | P0-4 |
| §三十三 RoutingSignals | 🟡 | 有复杂度正则，无信号聚合 |
| §三十四 TopicRegistry | ❌ | P1-6 |
| §三十五 安全优先 | ✅ | rule-first + 注入防御 |
| §三十六 错误处理 | 🟡 | 有 error 状态，缺 provider 级失败信息 |
| §三十七 缓存 | 🟡 | 有 TTL，无过期元数据 |
| §三十八 Source Policy | 🟡 | reliability_score 雏形 |
| §三十九 用户 PDF | ❌ | mock |
| §四十 Evidence Receipt | 🟡 | VerdictCard 已有大部分，缺 trace 链 |
| §四十一 README 重写 | 🟡 | 已重写（非 create-next-app），待补 Eval/Roadmap |
| §四十二 工程 Harness | 🟡 | 有 README/AGENTS/.env.example，缺 EVIDENCE_SPEC/SAFETY_RULES/EVAL/doctor |
| §四十三 测试 | ✅ | 154 测试 + 每模块测试 |
| §四十四/四十五 依赖策略 | ✅ | 无新框架，纯 Python |
| §四十六 分阶段迁移 | ✅ | 本流程 |
| §四十八 禁止伪完成 | ✅ | grounding 诚实标记 semantic_entailment_checked=False |

---

## 6. 审计验证记录

- `pytest backend/tests` → **154 passed**（2.07s）
- `vitest run` → **15 passed**（7 files）
- `tsc --noEmit` → 通过
- `next build` → 生产构建成功
- 端到端四路径（fast/deep/corpus/refused）均有 Verdict

---

*审计结束。下一步：生成 `docs/EVIDENCE_ENGINE_2_SPEC.md` + Golden Set + baseline。*
