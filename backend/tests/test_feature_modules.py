from app.feature_intent import extract_feature_intents, is_pure_feature_command
from app.orchestrator import OrchestrateInput, Orchestrator


def test_pure_profile_command_invokes_analysis_in_chat() -> None:
    run = Orchestrator().run(
        OrchestrateInput(
            session_id="feature-test",
            text="请综合分析一下我的身体状况",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )
    assert run.intent == "invoke_product_feature"
    assert len(run.module_plan) == 1
    assert run.module_plan[0].type == "ChatFeaturePanel"
    assert run.module_plan[0].props["feature"] == "health_profile_analysis"


def test_multiple_written_features_are_all_planned() -> None:
    intents = extract_feature_intents("显示今日记录，再打开16:8计时")
    assert {item.name for item in intents} == {"today_review", "fasting_timer"}
    assert is_pure_feature_command("显示今日记录，再打开16:8计时", intents)


def test_medical_answer_adds_bounded_tcm_card() -> None:
    run = Orchestrator().run(
        OrchestrateInput(
            session_id="tcm-test",
            text="地中海饮食对心血管风险有什么证据？",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )
    assert [item.type for item in run.module_plan] == ["EvidenceAnswer"]
    tcm = run.module_plan[0].props["tcm_perspective"]
    assert len(tcm["sources"]) >= 3
    assert "心血管" in tcm["topic_link"]
    assert tcm["ai_summary"]
    assert any(source["source_id"] == "TCM-SINOMED" for source in tcm["sources"])
    assert "不根据网页结果自行开方" in tcm["avoid"]
    assert "中医数据库只提供" in tcm["evidence_note"]


def test_refused_medical_request_does_not_add_tcm_treatment_card() -> None:
    run = Orchestrator().run(
        OrchestrateInput(
            session_id="tcm-refused-test",
            text="高血压能不能停药只吃低盐？",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )
    assert "tcm_perspective" not in run.module_plan[0].props


def test_non_tcm_question_skips_tcm_ai_call() -> None:
    """With an AI provider configured, non-TCM questions must keep the
    deterministic TCM card and skip the extra LLM round-trip."""

    calls: list[str] = []

    class CountingProvider:
        def select_model(self, question: str, mode: str = "auto") -> tuple[str, str]:
            return "model-x", "ai_fast"

        async def answer_health_question(
            self, question: str, *, model: str, evidence_blend=None
        ) -> object:
            from app.ai_provider import AIAnswer

            return AIAnswer(
                is_health_question=True,
                classification_reason="健康问题",
                conclusion="限钠有助于降压",
                explanation="减少过量钠摄入通常有助于降低血压。",
                evidence_strength="medium",
                target_population=["一般人群"],
                non_target_population=[],
                general_advice=["关注食品标签钠含量"],
                limitations=["个体反应存在差异"],
            )

        async def analyze_tcm_perspective(self, question, **kwargs) -> object:
            from app.ai_provider import TCMPerspectiveAnalysis

            calls.append(question)
            return TCMPerspectiveAnalysis(
                topic_link="地中海饮食与中医食疗的观察维度",
                perspective=["可以从整体饮食结构角度理解"],
                questions=["是否合并其他慢病"],
                safe_ideas=["保持饮食多样"],
                limitations=["中医视角不能替代现代证据"],
                ai_summary="现代证据为主，中医视角补充观察维度。",
            )

    run = Orchestrator(ai_provider=CountingProvider()).run(
        OrchestrateInput(
            session_id="tcm-skip-test",
            text="地中海饮食对心血管风险有什么证据？",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )
    tcm = run.module_plan[0].props["tcm_perspective"]
    assert calls == [], "non-TCM question must not call analyze_tcm_perspective"
    assert tcm["source"] == "deterministic_fallback"


def test_tcm_question_uses_ai_perspective() -> None:
    calls: list[str] = []

    class TCMProvider:
        def select_model(self, question: str, mode: str = "auto") -> tuple[str, str]:
            return "model-x", "ai_fast"

        async def answer_health_question(
            self, question: str, *, model: str, evidence_blend=None
        ) -> object:
            from app.ai_provider import AIAnswer

            return AIAnswer(
                is_health_question=True,
                classification_reason="健康问题",
                conclusion="限钠有助于降压",
                explanation="减少过量钠摄入通常有助于降低血压。",
                evidence_strength="medium",
                target_population=["一般人群"],
                non_target_population=[],
                general_advice=[],
                limitations=[],
            )

        async def analyze_tcm_perspective(self, question, **kwargs) -> object:
            from app.ai_provider import TCMPerspectiveAnalysis

            calls.append(question)
            return TCMPerspectiveAnalysis(
                topic_link="从中医食疗视角看限钠饮食",
                perspective=["低盐饮食与清淡饮食在中医语境有相近之处"],
                questions=["是否存在脾胃虚寒表现"],
                safe_ideas=["烹调时用葱姜蒜等天然调味"],
                limitations=["中医食疗不等于治疗"],
                ai_summary="现代证据为限钠降压提供主要依据。",
            )

    run = Orchestrator(ai_provider=TCMProvider()).run(
        OrchestrateInput(
            session_id="tcm-ai-test",
            text="中医怎么看限钠饮食？",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )
    tcm = run.module_plan[0].props["tcm_perspective"]
    assert calls == ["中医怎么看限钠饮食？"]
    assert tcm["source"] == "ai"
