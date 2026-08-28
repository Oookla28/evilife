# 「是非题」Evidence Engine 2.0 — 架构规格书

> 文档版本：v1.0
> 日期：2026-08-12
> 配套：`EVIDENCE_ENGINE_2_AUDIT.md`（现状审计）
> 原则：**保留 → 抽象 → 扩展 → 测试 → 迁移**；禁止推倒重写

---

## 1. 现状 → 目标

| 维度 | 现状（v1.x） | 目标（v2.0） |
|---|---|---|
| 输入 | 一句话 → 一个回答 | 一句话 → **多 Claim 拆解** → 每个 Claim 独立走证据链 |
| 检索 | DeepPath 静态拆包 + orchestrator 旁路联网 | DeepPath 成为**真正动态证据通路**（query gen → FOR/AGAINST → 去重 → rerank） |
| 验证 | Citation Integrity（id/url/数字） | Integrity + **Semantic Claim-Evidence Verifier** |
| 排序 | RRF 融合 | RRF + **Reranker**（相关/质量/人群/新鲜度/研究类型） |
| 证据表示 | EvidenceItem / VerdictEvidenceItem | **EvidenceNote**（supports/does_not_support/limitations 来自文献） |
| 结论 | conclusion + 4 值 Verdict | **6 值 Verdict + what_could_change_this_verdict + Evidence Receipt** |
| 可审计性 | timing_ms 4 个数字 | **Trace**（step/action/tool/observation/decision/latency） |
| 评测 | 无 | **Golden Set + Eval Harness + Badcase Registry**（A/B/C 基线） |
| 主题 | 2 个硬编码关键词 | **TopicRegistry**（data 驱动）+ RoutingSignals |

## 2. 目标架构

```text
User Input
    │
    ▼
[L2 Guardrails] InjectionDetector ──高/中危──► SafetyCard (injection_refusal)
    │
    ▼
ClaimDecomposer ──► Claim[]( 每条: {claim_id, claim, type, span, original_text} )
    │
    ▼
SafetyRouter (rule-first, 每条 Claim 独立评估)
    │
    ▼
RoutingSignals (risk / complexity / known_topic / packet_availability /
               packet_freshness / claim_count / population_boundary)
    │
    ├── REFUSE ──────────────────────────────► SafetyCard
    ├── FAST  ──► FastPath (golden Packet, 保底)
    └── DEEP  ──► DeepPath v2:
                    │
                    ├─ QueryGenerator ──► primary / synonym / clinical / boundary / contradiction
                    │        (MAX_QUERY_EXPANSION 上限)
                    ├─ EvidenceProvider ──► NCBI | EuropePMC | ClinicalTrials | Mock（Protocol 互换）
                    │        FOR query ─┐
                    │        AGAINST query ┘（独立记录 query/provider/timestamp/results）
                    ├─ Dedup ─► Rerank (ranker.py)
                    ├─ EvidenceNote 构建（supports / does_not_support / limitations 抽取）
                    ├─ CitationIntegrityVerifier（原 CitationVerifier，保留别名）
                    ├─ ClaimEvidenceVerifier（semantic：SUPPORTED/PARTIALLY/CONTRADICTED/INSUFFICIENT）
                    ├─ EvidenceGrade（strength + reasons）
                    ├─ Applicability（DIRECT/PARTIAL/UNCERTAIN/NOT_APPLICABLE）
                    ├─ ConflictDetector（人群/干预/结局/时间/质量维度）
                    ├─ EvidenceGate（不足即 abstain，禁止补全）
                    └─ Verdict（6 值 + receipt）
    │
    ▼
Trace（每步记录：step/action/tool/input_summary/output_summary/observation/decision/timestamp/latency/status）
    │
    ▼
SSE 流式事件（route → claim → search → snapshot → verify → gate → verdict → done）
    │
    ▼
前端：Polaroid 出纸语义化（max(min_print, evidence_ready) 驱动，非纯定时）
```

## 3. 新增模块与接口

### 3.1 `backend/app/claims/`（P0）
```text
claims/
├── models.py       # HealthClaim {claim_id, claim, type, span, original_text}
├── decomposer.py   # ClaimDecomposer: text → list[HealthClaim]（规则优先 + LLM 辅助 + MAX_CLAIMS）
├── worthiness.py   # ClaimWorthiness（可证伪性/可回答性/信息充分度）
└── normalizer.py   # 归一化（去重/合并/数值规范化）
```
接口：
```python
class ClaimDecomposer(Protocol):
    def decompose(self, text: str) -> list[HealthClaim]: ...
```
策略：规则（并列连词/分号/编号）→ LLM（`decompose_claims()` 结构化 JSON）→ 确定性过滤（worthiness、数量上限 `MAX_CLAIMS=5`）。

### 3.2 `backend/app/tools/`（P0）
```text
tools/
├── base.py         # EvidenceSource 模型 + EvidenceProvider Protocol + ToolError
├── europe_pmc.py   # EuropePMCProvider（迁移现有 EuropePMCSearch）
├── ncbi.py         # NCBIProvider（E-utilities, esearch+efetch，可选）
├── clinical_trials.py  # ClinicalTrialsProvider（v2 API，可选）
└── mock.py         # MockProvider（测试用，诚实标记）
```
```python
class EvidenceProvider(Protocol):
    async def search(self, query: str, *, direction: str, filters: dict) -> list[EvidenceSource]: ...
    async def fetch(self, source_id: str) -> EvidenceSource: ...
```
`EvidenceSource` 字段：source_id / source_database / title / authors / year / publication_date / source_type / journal_or_organization / pmid / doi / nct_id / url / abstract / population / intervention / comparator / outcome / retrieved_at。

**顺序**：先迁移 EuropePMC 到 Provider 接口（纯 Python Tool + 测试），NCBI/ClinicalTrials 后续加；MCP 仅作可选适配层。

### 3.3 `backend/app/evidence/` 扩展（P0/P1）
```text
evidence/
├── ranker.py           # EvidenceRanker（semantic/quality/recency/population/study_type/directness）
├── evidence_note.py    # EvidenceNote 模型 + 构建器（supports/does_not_support/limitations 抽取）
├── semantic_verifier.py# ClaimEvidenceVerifier: SUPPORTED/PARTIALLY_SUPPORTED/CONTRADICTED/INSUFFICIENT
│                       #   策略：deterministic rule → NLI（可选）→ LLM judge（最后手段）
├── grading.py          # EvidenceGrade（grade + reason + strengths + limitations；诚实命名 Evidence Strength）
├── applicability.py    # DIRECT/PARTIAL/UNCERTAIN/NOT_APPLICABLE
├── conflict.py         # EvidenceConflictDetector（维度分析）
└── citation_verifier.py# 保留；新增 CitationIntegrityVerifier 别名（兼容）
```

### 3.4 `backend/app/trace/`（P1）
```text
trace/
├── models.py   # TraceStep {step, action, tool, input_summary, output_summary, observation, decision, timestamp, latency, status}
└── recorder.py # TraceRecorder（进程内环形缓冲 + run_id 检索；禁止记录 CoT/Key/PHI）
```

### 3.5 Verdict 协议升级（P1）
```python
VerdictValue2 = Literal[
    "SUPPORTED", "MOSTLY_SUPPORTED", "CONTEXT_DEPENDENT",
    "MIXED_EVIDENCE", "NOT_SUPPORTED", "INSUFFICIENT_EVIDENCE",
]
# 保留旧 4 值作兼容映射（true→SUPPORTED 等）
# 新增字段：what_could_change_this_verdict: list[str]
```

### 3.6 数据模型（新增）
```text
data/topics/*.yaml        # TopicRegistry（每主题：id、keywords、packet_file、freshness、风险级别）
eval/datasets/golden_set.jsonl
eval/datasets/safety_cases.jsonl
eval/datasets/contradiction_cases.jsonl
eval/datasets/citation_cases.jsonl
eval/datasets/retrieval_cases.jsonl
eval/badcases.jsonl
```

## 4. 迁移计划（分阶段，每阶段实现→测试→汇报）

| Phase | 内容 | 交付物 | 依赖 |
|---|---|---|---|
| **0** | Audit + Spec + Golden Set + baseline | 本文档 + `docs/AUDIT` + `eval/datasets/*` | 无 |
| **1** | Data Models：Claims / EvidenceSource / EvidenceNote / Verdict v2 / Trace 模型 | `schemas.py` 扩展 + 测试 | 0 |
| **2** | Evidence Tools：EuropePMC 迁移到 Provider 接口 + Mock | `tools/` + 测试 | 1 |
| **3** | Dynamic Retrieval：DeepPath v2（query gen → FOR/AGAINST → dedup → rerank） | `deep_path.py` 重写（保留接口）+ `ranker.py` + 测试 | 1,2 |
| **4** | Verification：CitationIntegrityVerifier 别名 + ClaimEvidenceVerifier + Grading + Applicability + Conflict | `evidence/` 5 个新模块 + 测试 | 1,3 |
| **5** | Verdict v2 + Evidence Receipt + Gate 强化 | `verdict.py` 升级 + 测试 | 4 |
| **6** | Trace + SSE 真流式 + 前端动画语义化 | `trace/` + `main.py` + `app/lab` 改造 | 3,4,5 |
| **7** | Eval Harness：runner + A/B/C + Badcase Registry | `eval/run_eval.py` + 报告 | 0,5 |
| **8** | 前端集成：Claim 卡片 / Verdict 6 值渲染 / Trace 面板 | `components/` | 5,6 |
| **9** | 文档：README 重写 + EVIDENCE_SPEC/SAFETY_RULES/EVAL + doctor 脚本 | 文档 | 全部 |

**顺序纪律**：FastPath 全程保留；每阶段不破坏 154 个现有测试；新增模块必带测试。

## 5. 验收标准（每阶段通用）

- [ ] 现有 154 backend + 15 frontend 测试全绿（回归）
- [ ] 新增模块有单元测试 + 集成测试
- [ ] 无新框架依赖（除非 Phase 明确批准）
- [ ] 无 Mock 假装实现 / 假 DOI / 假引用
- [ ] 不安全内容不进入最终输出（Guardrails + Gate 全链路）
- [ ] 每阶段提交独立 commit（不混大 diff）

## 6. 风险与边界

- **Semantic Verifier 的可靠性**：LLM judge 本身可被误导 → 策略顺序 deterministic rule → NLI → LLM；LLM 输出必须结构化 + 二次校验。
- **实时文献可用性**：EuropePMC 可能限流/超时 → Provider 失败必须结构化返回 + 降级到缓存/语料库，前端可显示"PubMed 暂时不可用，已使用缓存证据"。
- **多 Claim 的 UI**：前端需支持 Claim 级卡片（1 输入 → N 卡片），CoverFlow 语义不变。
- **合规**：继续禁止诊断/处方/剂量；Verdict 的 CONTEXT_DEPENDENT 必须附 applies_to / does_not_apply_to。

---

*Spec 结束。下一步：Step 4 建立 Golden Set 与 baseline。*
