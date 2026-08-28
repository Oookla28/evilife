import asyncio

from app.ai_provider import AIAnswer, AIProvider, HealthSearchPlan


def test_ai_answer_normalizes_paragraph_arrays() -> None:
    answer = AIAnswer.model_validate(
        {
            "is_health_question": True,
            "classification_reason": "问题涉及睡眠健康。",
            "conclusion": ["第一段", "第二段"],
            "explanation": ["解释一", "解释二"],
            "evidence_strength": "low",
            "target_population": [],
            "non_target_population": [],
            "general_advice": [],
            "limitations": [],
        }
    )

    assert answer.conclusion == "第一段\n第二段"
    assert answer.explanation == "解释一\n解释二"


def test_ai_answer_requires_scope_classification() -> None:
    answer = AIAnswer.model_validate(
        {
            "is_health_question": False,
            "classification_reason": "这是编程问题。",
            "conclusion": "该问题不在医疗健康范围内。",
            "explanation": "请改问健康相关问题。",
            "evidence_strength": "insufficient",
        }
    )
    assert answer.is_health_question is False


def test_grounded_answer_can_report_high_evidence_strength() -> None:
    answer = AIAnswer.model_validate(
        {
            "is_health_question": True,
            "classification_reason": "问题属于医疗健康范围。",
            "conclusion": "该结论有高质量证据支持。",
            "explanation": "回答受可追溯来源约束。",
            "evidence_strength": "high",
        }
    )
    assert answer.evidence_strength == "high"


def test_health_search_plan_requires_traceable_search_query() -> None:
    plan = HealthSearchPlan.model_validate(
        {
            "is_health_question": True,
            "classification_reason": "问题涉及睡眠健康。",
            "search_query": "sleep duration adults systematic review",
            "risk_level": "low",
        }
    )
    assert "systematic review" in plan.search_query


def test_provider_parses_fenced_json_from_compatible_gateway() -> None:
    payload = AIProvider._parse_json_object('```json\n{"ok": true}\n```')
    assert payload == {"ok": True}


def test_provider_extracts_json_after_reasoning_prefix() -> None:
    payload = AIProvider._parse_json_object('分析完成。\n{"ok": true}')
    assert payload == {"ok": True}


def test_ai_answer_allows_empty_content_for_out_of_scope_request() -> None:
    answer = AIAnswer.model_validate(
        {
            "is_health_question": False,
            "classification_reason": "这是编程问题。",
            "conclusion": "",
            "explanation": "",
            "evidence_strength": "insufficient",
        }
    )
    assert answer.is_health_question is False


def test_general_answer_is_chinese_and_keeps_an_explicit_ethics_prompt(monkeypatch) -> None:
    ai = provider()
    captured: dict[str, str] = {}

    async def fake_request_json(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return {
            "answer": "牛顿第二定律通常写作 F = ma。",
            "key_points": ["合力决定加速度的变化。"],
            "limitations": [],
        }

    monkeypatch.setattr(ai, "_request_json", fake_request_json)
    answer = asyncio.run(
        ai.answer_general_question("解释牛顿第二定律", model="gpt-5.6-luna")
    )

    assert "F = ma" in answer.answer
    assert "受伦理边界约束" in captured["system_prompt"]
    assert "不得把回答包装成医疗建议" in captured["system_prompt"]
    assert "必须使用简体中文" in captured["system_prompt"]


def provider() -> AIProvider:
    return AIProvider(
        api_key="test-key",
        base_url="https://example.test",
        fast_model="gpt-5.6-luna",
        deep_model="gpt-5.6-terra",
    )


def test_auto_mode_uses_luna_for_normal_question() -> None:
    assert provider().select_model("如何改善睡眠？", "auto") == (
        "gpt-5.6-luna",
        "ai_fast",
    )


def test_auto_mode_uses_terra_for_complex_question() -> None:
    assert provider().select_model("孕妇同时服用多种药物，有哪些相互作用？", "auto") == (
        "gpt-5.6-terra",
        "ai_deep",
    )


def test_explicit_modes_override_complexity() -> None:
    ai = provider()
    assert ai.select_model("普通问题", "deep")[0] == "gpt-5.6-terra"
    assert ai.select_model("孕妇同时服用多种药物", "fast")[0] == "gpt-5.6-luna"


def test_health_answer_uses_warm_conversational_persona(monkeypatch) -> None:
    ai = provider()
    captured: dict[str, str] = {}

    async def fake_request_json(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return {
            "is_health_question": True,
            "classification_reason": "问题属于健康范围。",
            "conclusion": "目前证据不足。",
            "explanation": "需要更多可追溯来源。",
            "evidence_strength": "insufficient",
            "target_population": [],
            "non_target_population": [],
            "general_advice": [],
            "limitations": [],
        }

    monkeypatch.setattr(ai, "_request_json", fake_request_json)
    asyncio.run(
        ai.answer_health_question(
            "晚睡一定伤身体吗？",
            model="gpt-5.6-luna",
        )
    )

    prompt = captured["system_prompt"]
    assert "接地气、有亲切感" in prompt
    assert "像一个靠谱的朋友" in prompt
    assert "这套语气只改变表达方式，不改变事实标准" in prompt


def test_tcm_analysis_must_follow_the_question_and_not_invent_references(monkeypatch) -> None:
    ai = provider()
    captured: dict[str, str] = {}

    async def fake_request_json(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        captured["user_prompt"] = kwargs["user_prompt"]
        return {
            "topic_link": "针对地中海饮食与心血管风险，中医视角只补充饮食后感受与症状节律。",
            "perspective": ["观察饮食、睡眠与不适是否同步变化。"],
            "questions": ["餐后是否出现稳定不适？"],
            "safe_ideas": ["连续记录饮食和症状。"],
            "limitations": ["不能据此判定证型。"],
            "ai_summary": "临床证据约束疗效；中医只补充观察，不能确定证型。",
        }

    monkeypatch.setattr(ai, "_request_json", fake_request_json)
    result = asyncio.run(
        ai.analyze_tcm_perspective(
            "地中海饮食对心血管风险有什么证据？",
            model="gpt-5.6-luna",
            clinical_context={"conclusion": "可降低部分高风险人群的事件风险。"},
            source_context=[{"title": "一项临床研究", "role": "临床疗效"}],
        )
    )

    assert "地中海饮食" in result.topic_link
    assert "不要生成或复述参考文献列表" in captured["system_prompt"]
    assert "地中海饮食对心血管风险" in captured["user_prompt"]
