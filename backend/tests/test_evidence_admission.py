from app.evidence.admission import assess_evidence, boundary_direction


def test_direct_mediterranean_cvd_support_is_admitted() -> None:
    decision = assess_evidence(
        "地中海饮食可以降低心血管风险",
        title="Mediterranean diet and cardiovascular events",
        text="Mediterranean diet was associated with lower cardiovascular risk.",
    )
    assert decision.relevant is True
    assert decision.direction == "support"


def test_same_diet_but_wrong_outcome_is_rejected() -> None:
    decision = assess_evidence(
        "地中海饮食可以降低心血管风险",
        title="Mediterranean diet adherence in menopause",
        text="The study measured menopausal symptoms, quality of life and BMI.",
    )
    assert decision.relevant is False


def test_unrelated_diet_does_not_answer_egg_claim() -> None:
    decision = assess_evidence(
        "鸡蛋会增加心血管疾病风险吗",
        title="Mediterranean diet and cardiovascular disease",
        text="Mediterranean diet was associated with lower cardiovascular risk.",
    )
    assert decision.relevant is False


def test_direct_null_result_is_counterevidence() -> None:
    decision = assess_evidence(
        "16:8 限时进食能减重",
        title="Time-restricted eating and weight loss",
        text="Time-restricted eating showed no difference in body weight.",
    )
    assert decision.relevant is True
    assert decision.direction == "against"


def test_extrapolation_boundary_is_not_counterevidence() -> None:
    finding = "不能据此认为地中海饮食对所有人都同样有效，也不能替代治疗。"
    assert boundary_direction(
        "地中海饮食可以降低心血管风险", finding, "地中海饮食与心血管风险"
    ) == "context"


def test_boundary_refutes_absolute_but_not_universal_wording() -> None:
    finding = "不能据此认为地中海饮食对所有人都同样有效。"
    title = "地中海饮食与心血管风险"
    assert boundary_direction(
        "地中海饮食可以100%预防心血管疾病", finding, title
    ) == "against"
    assert boundary_direction(
        "地中海饮食对所有人都有效", finding, title
    ) == "context"
