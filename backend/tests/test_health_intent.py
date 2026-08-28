from app.health_intent import extract_observation_drafts, is_pure_record_intent
from app.orchestrator import OrchestrateInput, Orchestrator


def test_extracts_multiple_explicit_health_records() -> None:
    text = "帮我记一下：今天喝水1.5升，走了6,200步，昨晚睡了7小时30分钟，体重69.2公斤，腰围80厘米，静息心率65次/分，心情4分"
    drafts = extract_observation_drafts(text)
    values = {item.kind: item.value for item in drafts}
    assert values == {
        "water_ml": 1500,
        "steps": 6200,
        "sleep_minutes": 450,
        "weight_kg": 69.2,
        "waist_cm": 80,
        "resting_heart_rate": 65,
        "mood_score": 4,
    }
    assert is_pure_record_intent(text, drafts)


def test_general_question_is_not_mistaken_for_personal_record() -> None:
    assert extract_observation_drafts("每天走10000步是否健康？") == []


def test_mixed_personal_record_and_question_returns_two_modules() -> None:
    response = Orchestrator(ai_provider=None).run(
        OrchestrateInput(
            session_id="mixed-record",
            text="我今天走了5000步，限钠饮食对高血压有帮助吗？",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )
    assert [item.type for item in response.module_plan] == [
        "HealthRecordDraft",
        "EvidenceAnswer",
    ]
    assert "tcm_perspective" in response.module_plan[1].props
    assert response.actions[0].requires_confirmation is True


def test_pure_record_intent_returns_editable_draft_module() -> None:
    response = Orchestrator(ai_provider=None).run(
        OrchestrateInput(
            session_id="record-only",
            text="今天喝水800ml，走了3500步，帮我记一下",
            has_image=False,
            has_document=False,
            mode="auto",
        )
    )
    assert response.intent == "record_health_observations"
    assert response.module_plan[0].type == "HealthRecordDraft"
    assert len(response.module_plan[0].props["items"]) == 2
    assert response.actions[0].type == "save_health_observations"
