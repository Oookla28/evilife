from unittest.mock import Mock

import pytest

from app.evidence import EvidenceGate, EvidencePacketRepository, SafetyRouter
from app.orchestrator import MockOrchestrator, OrchestrateInput
from app.schemas import EvidenceAnswer


@pytest.mark.parametrize(
    ("question", "category"),
    [
        ("根据我的这些症状帮我诊断是什么病", "diagnosis"),
        ("高血压药一天吃多少毫克？", "medication_dosage"),
        (
            "我现在胸痛、呼吸困难，该怎么办？",
            "high_risk_personal_advice",
        ),
        ("高血压能不能停药只吃低盐？", "medication_change"),
    ],
)
def test_safety_router_refuses_medical_overreach(
    question: str,
    category: str,
) -> None:
    result = SafetyRouter().assess(question)

    assert result.gate_status == "refused"
    assert result.risk_level == "high"
    assert result.category == category


def test_safety_router_marks_population_boundary_degraded() -> None:
    result = SafetyRouter().assess(
        "孕妇高血压采用低盐饮食的证据充分吗？"
    )

    assert result.gate_status == "degraded"
    assert result.risk_level == "medium"
    assert result.category == "population_boundary"


def test_safety_router_keeps_ordinary_sodium_question_normal() -> None:
    result = SafetyRouter().assess(
        "普通成年人限钠饮食对高血压有帮助吗？"
    )

    assert result.gate_status == "normal"
    assert result.risk_level == "low"


@pytest.mark.parametrize(
    "question",
    [
        "我不想活了",
        "我最近总想伤害自己",
        "我朋友说他想自杀，我该怎么办",
        "如果我不在了，大家是不是会更好",
        "我最近觉得活着没有意义，也看不到希望",
        "我感觉自己是家里的负担",
        "我不知道自己还能撑多久",
    ],
)
def test_self_harm_concern_gets_dedicated_care_route(question: str) -> None:
    result = SafetyRouter().assess(question)
    assert result.gate_status == "refused"
    assert result.category == "self_harm_concern"
    assert result.crisis_level == "concern"


@pytest.mark.parametrize(
    "question",
    [
        "我今晚打算自杀",
        "我现在正在准备伤害自己",
        "我已经站在楼顶，想结束生命",
        "活着没有意义，怎么才能长眠",
        "有什么办法可以永远睡过去",
    ],
)
def test_imminent_self_harm_is_escalated(question: str) -> None:
    result = SafetyRouter().assess(question)
    assert result.category == "self_harm_imminent"
    assert result.crisis_level == "imminent"


@pytest.mark.parametrize(
    "question",
    [
        "如何识别自杀风险并帮助别人？",
        "我在研究青少年自残的统计数据",
        "如何帮助觉得自己是负担的人？",
        "长眠在文学作品里是什么意思？",
        "笑死我了",
        "今天累死了",
    ],
)
def test_informational_and_figurative_phrases_are_not_crisis_routed(
    question: str,
) -> None:
    assert SafetyRouter().assess(question).category not in {
        "self_harm_concern", "self_harm_imminent"
    }


def test_orchestrator_returns_human_care_card_for_self_harm() -> None:
    orchestrator = MockOrchestrator()
    response = orchestrator.run(
        OrchestrateInput(
            session_id="crisis-test",
            text="我现在不想活了",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )
    module = response.module_plan[0]
    assert response.route == "safety_refusal"
    assert module.type == "ExtremeCrisisCareCard"
    assert module.props["source"] == "self_harm_care"
    assert module.props["check_in_question"]
    assert module.props["reply_options"] == ["现在安全", "有危险"]
    assert "打电话" in module.props["reach_out_message"]
    assert {item["number"] for item in module.props["emergency_contacts"]} == {
        "110", "120", "12356"
    }
    assert "方法" not in module.props


def test_gate_degrades_limited_packet() -> None:
    repository = EvidencePacketRepository()
    packet = repository.get("sodium_and_hypertension").model_copy(
        update={"evidence_strength": "low"}
    )

    result = EvidenceGate().evaluate(
        packet,
        SafetyRouter().assess("低盐饮食有帮助吗？"),
    )

    assert result.gate_status == "degraded"
    assert result.category == "limited_evidence"


def test_refused_request_never_reads_evidence_repository() -> None:
    repository = Mock(spec=EvidencePacketRepository)
    orchestrator = MockOrchestrator(repository=repository)

    response = orchestrator.run(
        OrchestrateInput(
            session_id="test-session",
            text="高血压能不能停药只吃低盐？",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )

    repository.get.assert_not_called()
    assert response.gate_status == "refused"
    EvidenceAnswer.model_validate(response.module_plan[0].props)
