from __future__ import annotations

import asyncio
import inspect
import os
import re
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from .ai_provider import AIProvider, AIProviderError, GeneralAnswer
from .claims.decomposer import decompose
from .evidence import (
    DeepPath,
    EvidencePacketRepository,
    EvaluationModeRouter,
    FastPath,
    SafetyAssessment,
    SafetyRouter,
)
from .evidence.corpus import AuthoritativeCorpus
from .evidence.admission import extract_concepts
from .evidence.dynamic_pipeline import DynamicEvidencePipeline
from .evidence.grounding import verify_claims
from .evidence.verdict import build_verdict
from .evidence_blend import EvidenceBlend, EvidenceBlendService, citation_payloads
from .feature_intent import extract_feature_intents, is_pure_feature_command
from .guardrails import InjectionDetector, InjectionFinding
from .general_ethics import GeneralEthicsRouter
from .general_search import GeneralSearchError, GeneralWebSearch
from .health_intent import extract_observation_drafts, is_pure_record_intent
from .tools.europe_pmc import EuropePMCProvider
from .schemas import (
    Action,
    EvaluationMode,
    EvidenceAnswer,
    EvidenceQuerySet,
    ModulePlanItem,
    OrchestrateResponse,
    RouteName,
    Verdict,
)
from .tcm_evidence import build_tcm_perspective
from .trace.models import TraceRecorder


@dataclass(slots=True)
class OrchestrateInput:
    session_id: str
    text: str | None
    has_image: bool
    has_document: bool
    mode: str
    attachment_name: str | None = None
    attachment_content_type: str | None = None
    attachment_bytes: bytes | None = None


class Orchestrator:
    """Rule-first safety routing with packet, live-search and AI enrichment."""

    # Only questions with explicit TCM intent get the extra AI call; everyone
    # else gets the deterministic bounded TCM card for free.
    _TCM_INTENT_MARKERS = re.compile(
        r"中医|中药|药膳|食疗|体质|辨证|针灸|穴位|推拿|拔罐|艾灸|"
        r"养生|湿气|上火|寒性|热性|脾胃|气血|阴阳|脉象|舌苔|本草"
    )

    def __init__(
        self,
        repository: EvidencePacketRepository | None = None,
        ai_provider: AIProvider | None = None,
        blend_service: EvidenceBlendService | None = None,
        corpus: AuthoritativeCorpus | None = None,
        injection_detector: InjectionDetector | None = None,
        general_ethics_router: GeneralEthicsRouter | None = None,
        general_search: GeneralWebSearch | None = None,
    ) -> None:
        evidence_repository = repository or EvidencePacketRepository()
        self._fast_path = FastPath(evidence_repository)
        self._deep_path = DeepPath(evidence_repository)
        self._safety_router = SafetyRouter()
        self._mode_router = EvaluationModeRouter()
        self._ai_provider = ai_provider
        self._blend_service = blend_service or EvidenceBlendService(
            corpus=corpus
        )
        self._injection_detector = injection_detector or InjectionDetector()
        self._general_ethics = general_ethics_router or GeneralEthicsRouter()
        self._general_search = general_search
        # Phase 3: dynamic evidence pipeline (standalone; used to enrich the
        # deep/unknown paths with EvidenceNotes). Live provider only when
        # enabled; corpus channel always available.
        live_enabled = (
            os.getenv("EVILIFE_LIVE_SEARCH_ENABLED", "false").lower() == "true"
        )
        self._dynamic = DynamicEvidencePipeline(
            provider=EuropePMCProvider() if live_enabled else None,
        )

    def run(self, data: OrchestrateInput) -> OrchestrateResponse:
        """Synchronous compatibility entrypoint used by deterministic tests."""
        return asyncio.run(self.run_async(data))

    async def run_async(self, data: OrchestrateInput) -> OrchestrateResponse:
        started = perf_counter()
        request_id = f"req-{uuid4().hex[:12]}"
        run_id = f"run-{uuid4().hex[:12]}"
        module_id = f"m-{uuid4().hex[:8]}"
        trace = TraceRecorder(run_id)
        # Engine 2.0: decompose the input into traceable claims first.
        claims = decompose(data.text or "")
        trace.add(
            step="claim.parse",
            action="decompose",
            output_summary=(
                f"拆解出 {len(claims)} 条可证伪主张"
                if claims
                else "单条输入，无需拆分"
            ),
        )
        observation_drafts = (
            extract_observation_drafts(data.text)
            if not data.has_image and not data.has_document
            else []
        )
        record_module = (
            self._health_record_module(module_id, observation_drafts)
            if observation_drafts
            else None
        )
        feature_intents = (
            extract_feature_intents(data.text)
            if not data.has_image and not data.has_document
            else []
        )
        pure_feature_command = is_pure_feature_command(data.text, feature_intents)

        retrieve_ms = 0.0
        verify_ms = 0.0
        evidence_count = 0
        support_evidence_count = 0
        boundary_evidence_count = 0

        route_started = perf_counter()
        safety = self._safety_router.assess(data.text)
        selection = self._mode_router.select(data.mode, data.text, safety)
        normalized_mode: EvaluationMode = selection.mode
        route: RouteName = selection.route
        route_ms = round((perf_counter() - route_started) * 1000, 3)
        trace.add(
            step="safety.route", action="assess",
            output_summary=f"安全门={safety.gate_status} / 类别={safety.category}",
        )
        trace.add(
            step="route.select", action="route",
            output_summary=f"模式={normalized_mode} / 路由={route}",
        )

        # L2: prompt-injection / ethics-spoof scan runs before anything else
        # touches a model. High and medium findings are refused outright;
        # low findings (research framing) pass through unchanged.
        injection_findings = self._injection_detector.scan(data.text)
        blocking_findings = [
            finding
            for finding in injection_findings
            if finding.severity in {"high", "medium"}
        ]
        if safety.category in {"self_harm_concern", "self_harm_imminent"}:
            # A crisis disclosure always receives care first, even when its
            # wording also resembles an instruction-injection pattern.
            blocking_findings = []
        if blocking_findings:
            trace.add(
                step="guardrail.scan", action="block",
                output_summary=f"拦截注入/越狱：{blocking_findings[0].kind.value}",
                status="failed",
            )
            route = "injection_refusal"
            intent = "injection_refusal"
            risk_level = "high"
            module = self._injection_refusal_module(
                module_id, blocking_findings[0]
            )
            return OrchestrateResponse(
                request_id=request_id,
                session_id=data.session_id,
                run_id=run_id,
                intent=intent,
                risk_level=risk_level,
                gate_status="refused",
                status="running",
                module_plan=[module],
                actions=[],
                mode=normalized_mode,
                route=route,
                evidence_count=0,
                support_evidence_count=0,
                boundary_evidence_count=0,
                timing_ms={
                    "route_ms": route_ms,
                    "retrieve_ms": 0,
                    "verify_ms": 0,
                    "total_ms": round((perf_counter() - started) * 1000, 3),
                },
            )

        if data.has_document:
            intent = "summarize_document"
            risk_level = "low"
            route = "mock"
            module = ModulePlanItem(
                module_id=module_id,
                type="DocumentSummary",
                version="1",
                priority=1,
                status="ready",
                props={
                    "document_name": data.attachment_name or "uploaded-document",
                    "one_sentence_summary": (
                        "后端契约已接通；真实 PDF 解析与页码引用将在后续阶段启用。"
                    ),
                    "key_points": [
                        {
                            "title": "当前阶段",
                            "description": "仅验证上传、编排响应和动态模块契约。",
                        }
                    ],
                    "detailed_claims": [],
                },
            )
        elif data.has_image:
            intent = "analyze_meal"
            risk_level = "low"
            route = "mock"
            module = await self._meal_module(module_id, data)
        elif record_module is not None and is_pure_record_intent(data.text, observation_drafts):
            intent = "record_health_observations"
            risk_level = "low"
            route = "mock"
            module = record_module
        elif pure_feature_command:
            intent = "invoke_product_feature"
            risk_level = "low"
            route = "mock"
            module = self._feature_module(module_id, feature_intents[0])
        else:
            intent = "evidence_query"
            risk_level = safety.risk_level

            if safety.gate_status == "refused":
                route = "safety_refusal"
                module = (
                    self._self_harm_support_module(module_id, safety)
                    if safety.category in {
                        "self_harm_concern", "self_harm_imminent"
                    }
                    else self._refused_module(module_id, safety)
                )
            elif route == "general":
                module = self._general_module(module_id, safety)
            elif route in {"rag", "fast_path"}:
                result = self._fast_path.run(
                    data.text,
                    module_id=module_id,
                    safety=safety,
                )
                if result is None:
                    module, planned_risk, trusted_count = await self._unknown_module(
                        module_id, data, safety
                    )
                    risk_level = planned_risk or risk_level
                    evidence_count = trusted_count
                else:
                    module = await self._enrich_packet_module(
                        result.module,
                        packet=result.packet,
                        question=data.text or "",
                        mode=data.mode,
                    )
                    retrieve_ms = result.retrieve_ms
                    verify_ms = result.verify_ms
                    evidence_count = len(result.packet.evidence_items)
                    support_evidence_count = evidence_count
            else:
                result = self._deep_path.run(
                    data.text,
                    module_id=module_id,
                    safety=safety,
                )
                if result is None:
                    module, planned_risk, trusted_count = await self._unknown_module(
                        module_id, data, safety
                    )
                    risk_level = planned_risk or risk_level
                    evidence_count = trusted_count
                else:
                    module = await self._enrich_packet_module(
                        result.module,
                        packet=result.packet,
                        question=data.text or "",
                        mode=data.mode,
                        queries=result.dynamic_packet.queries,
                    )
                    retrieve_ms = result.retrieve_ms
                    verify_ms = result.verify_ms
                    evidence_count = len(result.packet.evidence_items)
                    verdict_props = module.props.get("verdict") or {}
                    support_evidence_count = len(
                        verdict_props.get("supporting_evidence") or []
                    )
                    boundary_evidence_count = len(
                        verdict_props.get("opposing_evidence") or []
                    )

        if (
            module.type == "EvidenceAnswer"
            and module.props.get("gate_status") != "refused"
        ):
            tcm_perspective = await self._build_tcm_perspective(
                data.text or "", data.mode, module.props
            )
            module = module.model_copy(
                update={
                    "props": {
                        **module.props,
                        "tcm_perspective": tcm_perspective,
                    }
                }
            )

        if module.type == "EvidenceAnswer":
            verdict_props = module.props.get("verdict") or {}
            verdict_support = len(verdict_props.get("supporting_evidence") or [])
            verdict_boundary = len(verdict_props.get("opposing_evidence") or [])
            support_evidence_count = verdict_support
            boundary_evidence_count = verdict_boundary
            if evidence_count == 0:
                evidence_count = verdict_support + verdict_boundary
            trace.add(
                step="evidence.compose",
                action="summarize",
                tool=module.props.get("source"),
                output_summary=(
                    f"支持证据 {verdict_support} 条，反对或边界证据 "
                    f"{verdict_boundary} 条，动态证据笔记 "
                    f"{len(module.props.get('dynamic_notes') or [])} 条"
                ),
                decision=(verdict_props.get("verdict_detail") or verdict_props.get("verdict")),
                status=(
                    "degraded"
                    if module.props.get("gate_status") == "degraded"
                    else "ok"
                ),
            )
        if pure_feature_command:
            module_plan = [
                self._feature_module(f"{module_id}-{index}", feature)
                for index, feature in enumerate(feature_intents, start=1)
            ]
        else:
            # Evidence/record answers stand alone: attaching a feature card
            # (e.g. FastingTimer) would hijack module_plan[0] and bury the
            # actual evidence answer.
            module_plan = [module]
        if record_module is not None and module is not record_module:
            module_plan.insert(0, record_module)
        # Attach Engine 2.0 observability to the final plan: decomposed
        # claims + evidence-chain trace.
        trace_steps = [step.model_dump(mode="json") for step in trace.snapshot()]
        claims_json = [claim.model_dump(mode="json") for claim in claims]
        for plan_module in module_plan:
            if plan_module.type == "EvidenceAnswer":
                plan_module.props["claims"] = claims_json
            plan_module.props["trace_steps"] = trace_steps
        actions = (
            [
                Action(
                    action_id=record_module.props["action_id"],
                    type="save_health_observations",
                    label="确认并添加健康记录",
                    requires_confirmation=True,
                    payload_preview={"items": record_module.props["items"]},
                )
            ]
            if record_module is not None
            else []
        )
        total_ms = round((perf_counter() - started) * 1000, 3)

        return OrchestrateResponse(
            request_id=request_id,
            session_id=data.session_id,
            run_id=run_id,
            intent=intent,
            risk_level=risk_level,
            gate_status=module.props.get("gate_status", "normal"),
            status="running",
            module_plan=module_plan,
            actions=actions,
            mode=normalized_mode,
            route=route,
            evidence_count=evidence_count,
            support_evidence_count=support_evidence_count,
            boundary_evidence_count=boundary_evidence_count,
            timing_ms={
                "route_ms": route_ms,
                "retrieve_ms": retrieve_ms,
                "verify_ms": verify_ms,
                "total_ms": total_ms,
            },
        )

    @staticmethod
    def _feature_module(module_id: str, feature) -> ModulePlanItem:
        if feature.module_type == "FastingTimer":
            return ModulePlanItem(
                module_id=f"{module_id}-fasting",
                type="FastingTimer",
                version="1",
                priority=0.9,
                status="ready",
                props={"gate_status": "normal"},
            )
        return ModulePlanItem(
            module_id=f"{module_id}-{feature.name}",
            type="ChatFeaturePanel",
            version="1",
            priority=0.9,
            status="ready",
            props={
                "feature": feature.name,
                "title": feature.title,
                "gate_status": "normal",
            },
        )

    @staticmethod
    def _health_record_module(module_id: str, drafts) -> ModulePlanItem:
        labels = {
            "water_ml": ("饮水", "ml"),
            "steps": ("步数", "步"),
            "sleep_minutes": ("睡眠", "分钟"),
            "weight_kg": ("体重", "kg"),
            "waist_cm": ("腰围", "cm"),
            "resting_heart_rate": ("静息心率", "次/分"),
            "mood_score": ("心情", "/ 5"),
        }
        action_id = f"action-{uuid4().hex[:8]}"
        return ModulePlanItem(
            module_id=f"{module_id}-records",
            type="HealthRecordDraft",
            version="1",
            priority=0.8,
            status="ready",
            props={
                "action_id": action_id,
                "items": [
                    {
                        "id": f"draft-{index}",
                        "kind": draft.kind,
                        "label": labels[draft.kind][0],
                        "unit": labels[draft.kind][1],
                        "value": draft.value,
                        "source_text": draft.source_text,
                    }
                    for index, draft in enumerate(drafts, start=1)
                ],
                "gate_status": "normal",
                "requires_confirmation": True,
            },
        )

    async def _meal_module(
        self,
        module_id: str,
        data: OrchestrateInput,
    ) -> ModulePlanItem:
        if self._ai_provider is None:
            return self._meal_error_module(
                module_id,
                "图片已收到，但视觉识别服务尚未配置，未生成餐食或热量数据。",
            )
        if not data.attachment_bytes or not data.attachment_content_type:
            return self._meal_error_module(
                module_id,
                "图片内容为空或格式无法读取，请重新粘贴一张清晰的餐食照片。",
            )
        try:
            analysis = await self._ai_provider.analyze_meal_image(
                data.attachment_bytes,
                content_type=data.attachment_content_type,
                question=data.text,
            )
        except AIProviderError:
            return self._meal_error_module(
                module_id,
                "视觉识别暂时失败，没有生成餐食记录。请稍后重试或换一张更清晰的图片。",
            )
        if not analysis.items:
            return self._meal_error_module(
                module_id,
                "图片里没有看到可识别的食物（可能是风景、文字截图，或食物被完全遮挡）。"
                "请拍一张主体清晰、光线充足的餐食照片。",
            )

        return ModulePlanItem(
            module_id=module_id,
            type="MealAnalyzer",
            version="1",
            priority=1,
            status="ready",
            props={
                "action_id": f"action-{uuid4().hex[:8]}",
                "items": [
                    {
                        "id": f"food-{index}",
                        **item.model_dump(mode="json"),
                    }
                    for index, item in enumerate(analysis.items, start=1)
                ],
                "total_calories": list(analysis.total_calories),
                "total_calories_center": analysis.total_calories_center,
                "overall_uncertainty": analysis.overall_uncertainty,
                "status": "ready",
            },
        )

    @staticmethod
    def _meal_error_module(module_id: str, message: str) -> ModulePlanItem:
        return ModulePlanItem(
            module_id=module_id,
            type="MealAnalyzer",
            version="1",
            priority=1,
            status="error",
            props={
                "action_id": f"action-{uuid4().hex[:8]}",
                "items": [],
                "total_calories": [0, 0],
                "status": "error",
                "gate_status": "degraded",
                "analysis_error": message,
            },
        )

    async def _enrich_packet_module(
        self,
        module: ModulePlanItem,
        *,
        packet,
        question: str,
        mode: str,
        queries: EvidenceQuerySet | None = None,
    ) -> ModulePlanItem:
        support_query = queries.support_query if queries else question
        boundary_query = queries.boundary_query if queries else question
        blend = await self._blend_service.build_bidirectional(
            question=question,
            support_query=support_query,
            boundary_query=boundary_query,
            mode=mode,
            packet=packet,
            topic=packet.topic,
        )
        if self._ai_provider is None:
            return self._attach_blend(
                module,
                blend,
                claim=question,
                conflict_detected=packet.conflict_detected,
            )

        model, ai_route = self._ai_provider.select_model(question, mode)
        try:
            answer_kwargs = {"model": model, "evidence_blend": blend}
            parameters = inspect.signature(
                self._ai_provider.answer_health_question
            ).parameters
            if "response_style" in parameters:
                answer_kwargs["response_style"] = (
                    "professional" if mode == "evaluation" else "life"
                )
            answer = await self._ai_provider.answer_health_question(
                question, **answer_kwargs
            )
            if not answer.is_health_question:
                return self._attach_blend(
                    module,
                    blend,
                    claim=question,
                    conflict_detected=packet.conflict_detected,
                )
            props = self._answer_props(
                answer=answer,
                blend=blend,
                source=f"hybrid_{ai_route}",
                model=model,
                evidence_strength=packet.evidence_strength,
                packet_id=packet.packet_id,
                topic=packet.topic,
                base_gate_status=module.props.get("gate_status", "normal"),
                claim=question,
                conflict_detected=packet.conflict_detected,
                applies_to=[item.population for item in packet.evidence_items],
                does_not_apply_to=[
                    entry.finding for entry in blend.opposing_evidence
                ],
                limitations=[
                    *(item.limitations for item in packet.evidence_items),
                    *(packet.missing_evidence or []),
                ],
            )
            for key in ("dynamic_packet_id", "queries"):
                if key in module.props:
                    props[key] = module.props[key]
            return module.model_copy(update={"props": props})
        except AIProviderError:
            return self._attach_blend(
                module,
                blend,
                claim=question,
                conflict_detected=packet.conflict_detected,
            )

    async def _build_tcm_perspective(
        self,
        question: str,
        mode: str,
        evidence_props: dict,
    ) -> dict:
        fallback = build_tcm_perspective(question, evidence_props)
        if self._ai_provider is None:
            return fallback
        if not self._TCM_INTENT_MARKERS.search(question or ""):
            # Non-TCM questions keep the deterministic card; skip the extra
            # LLM round-trip entirely (one fewer call per answer).
            return fallback

        model, _ = self._ai_provider.select_model(question, mode)
        clinical_context = {
            "conclusion": evidence_props.get("conclusion"),
            "explanation": evidence_props.get("explanation"),
            "general_advice": evidence_props.get("general_advice") or [],
            "limitations": evidence_props.get("limitations") or [],
            "evidence_strength": evidence_props.get("evidence_strength"),
            "evidence_mix": evidence_props.get("evidence_mix") or {},
        }
        try:
            analysis = await self._ai_provider.analyze_tcm_perspective(
                question,
                model=model,
                clinical_context=clinical_context,
                source_context=fallback["sources"],
            )
        except AIProviderError:
            return fallback

        return {
            **fallback,
            **analysis.model_dump(),
            "summary": analysis.topic_link,
            "source": "ai",
        }

    async def _unknown_module(
        self,
        module_id: str,
        data: OrchestrateInput,
        safety: SafetyAssessment,
    ) -> tuple[ModulePlanItem, str | None, int]:
        """Unknown-topic path + Phase 3 dynamic EvidenceNotes enrichment."""
        if not data.text:
            return await self._unknown_inner(module_id, data, safety)

        claims = decompose(data.text)
        if not claims:
            from .claims.models import HealthClaim

            claims = [
                HealthClaim(
                    claim_id="C0",
                    claim=data.text.strip(),
                    type="other",
                    original_text=data.text.strip(),
                    source_intent=data.text.strip(),
                )
            ]

        # The answer/blend path and the structured EvidenceNote pipeline are
        # independent. Run them together so live literature latency is paid
        # once instead of serially; dynamic enrichment remains best-effort.
        inner_result, dynamic_result = await asyncio.gather(
            self._unknown_inner(module_id, data, safety),
            self._dynamic.run(claims[0]),
            return_exceptions=True,
        )
        if isinstance(inner_result, BaseException):
            raise inner_result
        module, planned_risk, trusted_count = inner_result
        if (
            module.type == "EvidenceAnswer"
            and not isinstance(dynamic_result, BaseException)
            and dynamic_result.notes
        ):
            module = module.model_copy(
                update={
                    "props": {
                        **module.props,
                        "dynamic_notes": [
                            note.model_dump(mode="json")
                            for note in dynamic_result.notes
                        ],
                    }
                }
            )
        return module, planned_risk, trusted_count

    async def _unknown_inner(
        self,
        module_id: str,
        data: OrchestrateInput,
        safety: SafetyAssessment,
    ) -> tuple[ModulePlanItem, str | None, int]:
        if not data.text:
            return self._fallback_module(module_id, safety), None, 0
        if self._ai_provider is None:
            # Offline Dynamic Evidence Engine: even without an LLM, the
            # curated corpus + live search still produce a bidirectional
            # evidence answer and a claim-level verdict.
            blend = await self._blend_service.build_bidirectional(
                question=data.text,
                support_query=data.text,
                boundary_query=data.text,
                mode=data.mode,
                topic=None,
            )
            if blend.supporting_evidence or blend.opposing_evidence:
                module = self._corpus_evidence_module(
                    module_id, data.text, blend, safety
                )
                return module, None, len(blend.trusted_sources)
            return self._fallback_module(module_id, safety), None, 0

        model, ai_route = self._ai_provider.select_model(data.text, data.mode)
        try:
            plan = await self._ai_provider.plan_health_question(
                data.text,
                model=model,
            )
            if not plan.is_health_question:
                return await self._general_answer_module(
                    module_id,
                    data.text,
                    plan.classification_reason,
                    model,
                    search_query=plan.search_query,
                ), plan.risk_level, 0

            blend = await self._blend_service.build_bidirectional(
                question=data.text,
                support_query=plan.search_query,
                boundary_query=plan.search_query,
                mode=data.mode,
                topic=None,
            )
            answer = await self._ai_provider.answer_health_question(
                data.text,
                model=model,
                evidence_blend=blend,
                response_style=(
                    "professional" if data.mode == "evaluation" else "life"
                ),
            )
            if not answer.is_health_question:
                return await self._general_answer_module(
                    module_id,
                    data.text,
                    answer.classification_reason,
                    model,
                    search_query=data.text,
                ), plan.risk_level, len(blend.trusted_sources)
            return ModulePlanItem(
                module_id=module_id,
                type="EvidenceAnswer",
                version="1",
                priority=1,
                status="ready",
                props=self._answer_props(
                    answer=answer,
                    blend=blend,
                    source=f"hybrid_{ai_route}",
                    model=model,
                    base_gate_status=safety.gate_status,
                    claim=data.text,
                    conflict_detected=Orchestrator._has_direct_conflict(blend),
                    applies_to=answer.target_population,
                    does_not_apply_to=answer.non_target_population,
                    limitations=answer.limitations,
                ),
            ), plan.risk_level, len(blend.trusted_sources)
        except AIProviderError:
            return self._fallback_module(module_id, safety), None, 0

    async def _general_answer_module(
        self,
        module_id: str,
        question: str,
        classification_reason: str,
        model: str,
        search_query: str | None = None,
    ) -> ModulePlanItem:
        ethics = self._general_ethics.assess(question)
        if not ethics.allowed:
            return ModulePlanItem(
                module_id=module_id,
                type="GeneralAnswerCard",
                version="1",
                priority=1,
                status="ready",
                props={
                    "title": "这部分不能提供操作性帮助",
                    "answer": (
                        f"{ethics.reason}。如果你的目的是学习、防范、求助或合规研究，"
                        "可以换成不包含实施步骤的问题，我会继续帮你。"
                    ),
                    "classification_reason": classification_reason,
                    "key_points": [],
                    "limitations": [
                        "不会提供可直接实施伤害、违法、欺诈或侵犯隐私的步骤。",
                        "可以讨论风险识别、防范、法律与伦理背景。",
                    ],
                    "boundary_status": "blocked",
                    "boundary_label": "伦理边界禁止",
                    "gate_status": "refused",
                    "source": "general_ethics_gate",
                    "model": model,
                },
            )

        web_query = (search_query or "").strip()
        if not web_query or web_query.lower() == "not_applicable":
            web_query = question
        search_results = []
        search_status = "disabled"
        if self._general_search is not None:
            try:
                search_results = await self._general_search.search(web_query)
                search_status = "ok" if search_results else "empty"
            except GeneralSearchError:
                search_status = "failed"

        try:
            answer = await self._ai_provider.answer_general_question(
                question,
                model=model,
                search_results=search_results,
            )
        except (AIProviderError, AttributeError):
            return self._general_unavailable_card(
                module_id, classification_reason, model
            )
        return self._general_answer_card(
            module_id,
            answer,
            classification_reason,
            model,
            search_results=[item.model_dump(mode="json") for item in search_results],
            search_status=search_status,
            search_query=web_query,
        )

    @staticmethod
    def _general_answer_card(
        module_id: str,
        answer: GeneralAnswer,
        classification_reason: str,
        model: str,
        search_results: list[dict],
        search_status: str,
        search_query: str,
    ) -> ModulePlanItem:
        return ModulePlanItem(
            module_id=module_id,
            type="GeneralAnswerCard",
            version="1",
            priority=1,
            status="ready",
            props={
                "title": "非医学通用回答",
                "answer": answer.answer,
                "classification_reason": classification_reason,
                "key_points": answer.key_points,
                "limitations": answer.limitations,
                "boundary_status": "limited",
                "boundary_label": "伦理边界开启",
                "gate_status": "degraded",
                "status": "ready",
                "source": "bounded_general_ai",
                "model": model,
                "search_results": search_results,
                "search_status": search_status,
                "search_query": search_query,
            },
        )

    @staticmethod
    def _general_unavailable_card(
        module_id: str,
        classification_reason: str,
        model: str,
    ) -> ModulePlanItem:
        return ModulePlanItem(
            module_id=module_id,
            type="GeneralAnswerCard",
            version="1",
            priority=1,
            status="ready",
            props={
                "title": "非医学通用回答暂不可用",
                "answer": "当前大模型没有返回可验证的通用回答，请稍后再试。",
                "classification_reason": classification_reason,
                "key_points": [],
                "limitations": ["系统不会用医疗证据卡伪装成通用回答。"],
                "boundary_status": "unavailable",
                "boundary_label": "未进入医疗证据引擎",
                "gate_status": "degraded",
                "source": "general_ai_unavailable",
                "model": model,
            },
        )

    @staticmethod
    def _corpus_evidence_module(
        module_id: str,
        question: str,
        blend: EvidenceBlend,
        safety: SafetyAssessment,
    ) -> ModulePlanItem:
        """Offline bidirectional answer built from corpus + live evidence."""
        support = blend.supporting_evidence
        oppose = blend.opposing_evidence
        direct_oppose = [
            item for item in oppose if item.direction in {"against", "mixed"}
        ]
        if support and direct_oppose:
            conclusion = (
                "现有可追溯证据对这个问题存在分歧，"
                "结论需要按人群和条件分别看待。"
            )
        elif support:
            conclusion = (
                "现有可追溯证据总体支持这个方向；"
                "同时存在适用范围或外推边界。"
                if oppose
                else "现有可追溯证据总体支持这个方向。"
            )
        elif direct_oppose:
            conclusion = "现有可追溯证据暂不支持该主张。"
        else:
            conclusion = "当前没有足够可追溯证据支撑结论。"

        explanation_parts = [item.finding for item in support[:2]]
        explanation_parts.append(
            f"同时检索到 {len(oppose)} 条反对或边界证据："
            if oppose
            else "未检索到明确的反对或边界证据。"
        )
        explanation_parts.extend(item.finding for item in oppose[:2])
        explanation = "；".join(
            part for part in explanation_parts if part and part != "同时检索到 0 条反对或边界证据："
        )

        if support and not direct_oppose:
            broad_without_subject = not extract_concepts(question)["subject"]
            if broad_without_subject and len(support) < 2:
                strength = "insufficient"
                gate = "degraded"
            else:
                strength = "medium" if len(support) >= 2 else "low"
                gate = "normal" if len(support) >= 2 else "degraded"
        elif support and direct_oppose:
            strength = "low"
            gate = "degraded"
        elif direct_oppose:
            strength = (
                "medium"
                if len(direct_oppose) >= 2
                else "low"
                if extract_concepts(question)["subject"]
                else "insufficient"
            )
            gate = "degraded"
        else:
            strength = "insufficient"
            gate = "degraded"

        verdict = Orchestrator._make_verdict(
            claim=question,
            blend=blend,
            gate_status=gate,
            evidence_strength=strength,
            conflict_detected=bool(support and direct_oppose),
            applies_to=[],
            does_not_apply_to=[item.finding for item in oppose[:3]],
            limitations=[
                "该主题暂无预编译证据包，结论来自本地语料与实时检索的首次合成。",
                "语料主张为人工审核摘要，仍需回到原始文献核对细节。",
            ],
        )
        answer = EvidenceAnswer(
            conclusion=conclusion,
            gate_status=gate,  # type: ignore[arg-type]
            evidence_strength=strength,  # type: ignore[arg-type]
            explanation=explanation or conclusion,
            target_population=[],
            non_target_population=[item.finding for item in oppose[:3]],
            general_advice=[],
            limitations=[
                "该主题暂无预编译证据包，结论来自本地语料与实时检索的首次合成。",
                "语料主张为人工审核摘要，仍需回到原始文献核对细节。",
            ],
            citations=citation_payloads(blend),
            verdict=verdict,
        )
        module = Orchestrator._evidence_module(module_id, answer)
        return module.model_copy(
            update={
                "props": {
                    **module.props,
                    "source": "hybrid_corpus",
                    "evidence_mix": blend.metadata(),
                    "grounding": verify_claims(
                        [
                            {
                                "text": claim,
                                "citations": [
                                    source.source_id
                                    for source in blend.trusted_sources
                                ],
                            }
                            for claim in (
                                conclusion,
                                explanation,
                            )
                            if claim.strip()
                        ],
                        known_source_ids=[
                            source.source_id
                            for source in blend.trusted_sources
                        ],
                        allowed_source_ids=[
                            source.source_id
                            for source in blend.trusted_sources
                        ],
                    ),
                }
            }
        )

    @staticmethod
    def _fallback_module(
        module_id: str,
        safety: SafetyAssessment,
    ) -> ModulePlanItem:
        limitations = ["尚无与该问题匹配的预编译 Evidence Packet。"]
        if safety.gate_status == "degraded":
            limitations.insert(0, safety.reason)
        answer = EvidenceAnswer(
            conclusion="这个问题咱们目前还不能硬下循证结论。",
            gate_status="degraded",
            evidence_strength="insufficient",
            explanation="咱们暂时没找到能对得上的可靠证据，不能靠猜；把证据补齐了，再继续往下聊。",
            target_population=[],
            non_target_population=[],
            general_advice=[],
            limitations=limitations,
            citations=[],
            # Abstain semantics (spec §20): insufficient evidence must still
            # produce a verdict — INSUFFICIENT_EVIDENCE — never a missing one.
            verdict=build_verdict(
                claim="当前问题暂无可靠证据支持",
                supporting=[],
                opposing=[],
                evidence_strength="insufficient",
                gate_status="degraded",
                conflict_detected=False,
                applies_to=[],
                does_not_apply_to=[],
                limitations=limitations,
            ),
        )
        module = Orchestrator._evidence_module(module_id, answer)
        return module.model_copy(
            update={
                "props": {
                    **module.props,
                    "source": "fallback",
                    "evidence_mix": {
                        "reliable_weight": 0.0,
                        "general_weight": 1.0,
                        "target_reliable_weight": 0.78,
                        "policy_reason": "没有可追溯来源，输出已降级。",
                        "live_search_status": "disabled",
                        "trusted_source_count": 0,
                    },
                }
            }
        )

    @staticmethod
    def _answer_props(
        *,
        answer,
        blend: EvidenceBlend,
        source: str,
        model: str,
        base_gate_status: str,
        evidence_strength: str | None = None,
        packet_id: str | None = None,
        topic: str | None = None,
        claim: str | None = None,
        conflict_detected: bool = False,
        applies_to: list[str] | None = None,
        does_not_apply_to: list[str] | None = None,
        limitations: list[str] | None = None,
    ) -> dict:
        grounding = Orchestrator._ground_answer(answer, blend)
        gate_status = (
            "degraded"
            if (
                base_gate_status == "degraded"
                or blend.reliable_weight < 0.75
                or not grounding["grounded"]
            )
            else "normal"
        )
        resolved_strength = evidence_strength or answer.evidence_strength
        verdict = Orchestrator._make_verdict(
            claim=claim or answer.conclusion,
            blend=blend,
            gate_status=gate_status,
            evidence_strength=resolved_strength,
            conflict_detected=conflict_detected,
            applies_to=applies_to or answer.target_population,
            does_not_apply_to=does_not_apply_to or answer.non_target_population,
            limitations=limitations or answer.limitations,
        )
        props = {
            **answer.model_dump(
                exclude={"is_health_question", "classification_reason"}
            ),
            "evidence_strength": resolved_strength,
            "gate_status": gate_status,
            "citations": citation_payloads(blend),
            "status": "ready",
            "source": source,
            "model": model,
            "scope_reason": answer.classification_reason,
            "evidence_mix": blend.metadata(),
            "grounding": grounding,
            "verdict": verdict.model_dump(mode="json"),
        }
        if packet_id:
            props["packet_id"] = packet_id
        if topic:
            props["topic"] = topic
        return props

    @staticmethod
    def _make_verdict(
        *,
        claim: str,
        blend: EvidenceBlend,
        gate_status: str,
        evidence_strength: str,
        conflict_detected: bool,
        applies_to: list[str],
        does_not_apply_to: list[str],
        limitations: list[str],
    ) -> Verdict:
        return build_verdict(
            claim=claim,
            supporting=blend.supporting_evidence,
            opposing=blend.opposing_evidence,
            evidence_strength=evidence_strength,  # type: ignore[arg-type]
            gate_status=gate_status,  # type: ignore[arg-type]
            conflict_detected=conflict_detected,
            applies_to=applies_to,
            does_not_apply_to=does_not_apply_to,
            limitations=limitations,
        )

    @staticmethod
    def _has_direct_conflict(blend: EvidenceBlend) -> bool:
        return bool(blend.supporting_evidence) and any(
            item.direction in {"against", "mixed"}
            for item in blend.opposing_evidence
        )

    @staticmethod
    def _attach_blend(
        module: ModulePlanItem,
        blend: EvidenceBlend,
        claim: str | None = None,
        conflict_detected: bool | None = None,
    ) -> ModulePlanItem:
        source_ids = [source.source_id for source in blend.trusted_sources]
        claims = [
            module.props.get("conclusion", ""),
            module.props.get("explanation", ""),
            *module.props.get("general_advice", []),
        ]
        grounding = verify_claims(
            [
                {"text": claim, "citations": source_ids}
                for claim in claims
                if isinstance(claim, str) and claim.strip()
            ],
            known_source_ids=source_ids,
            allowed_source_ids=source_ids,
        )
        verdict = Orchestrator._make_verdict(
            claim=claim or module.props.get("conclusion", ""),
            blend=blend,
            gate_status=module.props.get("gate_status", "degraded"),
            evidence_strength=module.props.get("evidence_strength", "insufficient"),
            conflict_detected=(
                Orchestrator._has_direct_conflict(blend)
                if conflict_detected is None
                else conflict_detected or Orchestrator._has_direct_conflict(blend)
            ),
            applies_to=module.props.get("target_population", []),
            does_not_apply_to=module.props.get("non_target_population", []),
            limitations=module.props.get("limitations", []),
        )
        return module.model_copy(
            update={
                "props": {
                    **module.props,
                    "citations": citation_payloads(blend),
                    "source": "hybrid_fast_path",
                    "evidence_mix": blend.metadata(),
                    "grounding": grounding,
                    "verdict": verdict.model_dump(mode="json"),
                }
            }
        )

    @staticmethod
    def _ground_answer(answer, blend: EvidenceBlend) -> dict:
        source_ids = [source.source_id for source in blend.trusted_sources]
        claims = [
            answer.conclusion,
            answer.explanation,
            *answer.general_advice,
        ]
        return verify_claims(
            [
                {"text": claim, "citations": source_ids}
                for claim in claims
                if claim.strip()
            ],
            known_source_ids=source_ids,
            allowed_source_ids=source_ids,
        )

    @staticmethod
    def _injection_refusal_module(
        module_id: str,
        finding: InjectionFinding,
    ) -> ModulePlanItem:
        """Block an adversarial input before it reaches any model call."""
        labels = {
            "direct": "检测到试图覆盖系统指令的输入",
            "extraction": "检测到试图提取系统指令或内部配置的输入",
            "jailbreak": "检测到越狱式角色扮演或解除限制的输入",
            "ethics_spoof": "检测到试图用身份或授权绕过伦理边界的输入",
            "encoded": "检测到编码混淆的注入内容",
            "obfuscated": "检测到疑似错拼变体的注入内容",
            "indirect": "检测到文档内容中包含指令性内容",
        }
        return ModulePlanItem(
            module_id=module_id,
            type="SafetyCard",
            version="1",
            priority=1,
            status="ready",
            props={
                "title": "这条输入咱不处理",
                "message": (
                    f"{labels.get(finding.kind.value, '检测到可疑指令')}。"
                    "系统只按既定证据流程回答健康问题，不执行输入中夹带的任何指令。"
                    "你可以换一种正常问法继续。"
                ),
                "severity": "high" if finding.severity == "high" else "medium",
                "gate_status": "refused",
                "status": "ready",
                "source": "injection_guard",
                "finding_kind": finding.kind.value,
                "finding_detail": finding.message,
            },
        )

    @staticmethod
    def _refused_module(
        module_id: str,
        safety: SafetyAssessment,
    ) -> ModulePlanItem:
        answer = EvidenceAnswer(
            conclusion="这类涉及诊断、停药、改药、药物剂量或高风险个人医疗的建议，咱不能直接拍板。",
            gate_status="refused",
            evidence_strength="insufficient",
            explanation=f"原因很简单：{safety.reason}",
            target_population=[],
            non_target_population=[],
            general_advice=[
                "先别擅自停药、改药或调整剂量，带着病史和当前治疗去找专业医生一起判断。",
                "如果有可能危及生命的急症迹象，别等线上回答，立刻联系当地急救服务。",
            ],
            limitations=["这个工具只做健康信息和证据概括，不替代诊断或个体化治疗。"],
            citations=[],
            verdict=build_verdict(
                claim="这个问题属于不适合直接裁决的医疗决策",
                supporting=[],
                opposing=[],
                evidence_strength="insufficient",
                gate_status="refused",
                conflict_detected=False,
                applies_to=[],
                does_not_apply_to=[],
                limitations=[safety.reason],
            ),
        )
        return Orchestrator._evidence_module(module_id, answer)

    @staticmethod
    def _self_harm_support_module(
        module_id: str,
        safety: SafetyAssessment,
    ) -> ModulePlanItem:
        imminent = safety.crisis_level == "imminent"
        return ModulePlanItem(
            module_id=module_id,
            type="ExtremeCrisisCareCard" if imminent else "CrisisSupportCard",
            version="1",
            priority=1,
            status="ready",
            props={
                "title": (
                    "我认真看到了这句话。现在先让人来到你身边"
                    if imminent
                    else "谢谢你愿意把这句话交给我。先别一个人扛"
                ),
                "message": (
                    "我不会评判你，也不需要你现在把所有事情解释清楚。你提到了明确的危险，"
                    "所以此刻只做一件事：停下可能伤害自己的动作，离开危险位置，让现实中的人马上到你身边。"
                    if imminent
                    else "听起来你已经难受了一段时间。我不会急着分析你、责怪你，也不会拿大道理压你。"
                    "现在最重要的不是把一切想通，而是先确认你此刻是否安全，再找一个真实的人陪你。"
                ),
                "severity": "high",
                "gate_status": "refused",
                "status": "ready",
                "source": "self_harm_care",
                "crisis_level": safety.crisis_level or "concern",
                "check_in_question": (
                    "你只要先回答一句：已经有危险，还是现在暂时安全？"
                    if imminent
                    else "你可以只回复一句：“现在安全”或“有危险”。"
                ),
                "reply_options": ["现在安全", "有危险"],
                "reach_out_message": (
                    "我现在可能会伤害自己。请马上给我打电话或来陪我，"
                    "并帮我联系急救或报警，不要让我一个人待着。"
                    if imminent
                    else "我现在状态很差，一个人有点撑不住。你能现在给我打个电话，"
                    "或者来陪我待一会儿吗？"
                ),
                "immediate_steps": [
                    "把上面的求助话术直接发给一个你信任的人，请对方到你身边或保持通话。",
                    "离开楼顶、马路、水边等危险位置，把药物、刀具或其他危险物品交给别人保管。",
                    "如果已经有行动、工具或明确计划，请立即拨打 120 或 110；也可以请身边的人代打。",
                    "还没有迫在眉睫的危险时，也可以拨打全国统一心理援助热线 12356。",
                ],
                "supportive_note": (
                    "你不需要现在解决整个人生。咱们先把接下来的十分钟安全地过完，然后再处理下一件事。"
                ),
                "avoid_actions": [
                    "不要独自前往危险地点。",
                    "不要继续饮酒或使用会降低判断力的物质。",
                    "不要仅依赖网页或 AI；请尽快连接现实中的人和专业支持。",
                ],
                "emergency_contacts": [
                    {"label": "医疗急救", "number": "120"},
                    {"label": "报警求助", "number": "110"},
                    {"label": "全国统一心理援助热线", "number": "12356"},
                ],
                "reason": safety.reason,
            },
        )

    @staticmethod
    def _general_module(
        module_id: str,
        safety: SafetyAssessment,
    ) -> ModulePlanItem:
        limitations = ["general 评测模式不检索 Evidence Packet。"]
        if safety.gate_status == "degraded":
            limitations.insert(0, safety.reason)
        answer = EvidenceAnswer(
            conclusion="当前 general 模式不能生成可验证的循证结论。",
            gate_status="degraded",
            evidence_strength="insufficient",
            explanation="该模式仅保留统一入口和基础安全检查作为评测骨架。",
            target_population=[],
            non_target_population=[],
            general_advice=[],
            limitations=limitations,
            citations=[],
        )
        return Orchestrator._evidence_module(module_id, answer)

    @staticmethod
    def _evidence_module(
        module_id: str,
        answer: EvidenceAnswer,
    ) -> ModulePlanItem:
        return ModulePlanItem(
            module_id=module_id,
            type="EvidenceAnswer",
            version="1",
            priority=1,
            status="ready",
            props=answer.model_dump(mode="json", exclude_none=True),
        )


MockOrchestrator = Orchestrator
