from app.ai_provider import MealAnalysis, MealAnalysisItem
from app.orchestrator import OrchestrateInput, Orchestrator


class FakeVisionProvider:
    async def analyze_meal_image(
        self,
        image_bytes: bytes,
        *,
        content_type: str,
        question: str | None = None,
    ) -> MealAnalysis:
        assert image_bytes == b"valid-image"
        assert content_type == "image/png"
        assert question == "帮我看看这顿饭"
        return MealAnalysis(
            items=[
                MealAnalysisItem(
                    name="米饭",
                    portion="约一小碗",
                    portion_grams=(150, 180),
                    estimated_calories=(180, 240),
                    estimated_calories_center=210,
                    confidence="medium",
                    reference_basis="按熟米饭估计重量与常见能量密度换算。",
                    uncertainty="碗的大小和米饭重量无法从单张图片精确判断。",
                )
            ],
            total_calories=(180, 240),
            total_calories_center=210,
            overall_uncertainty="图片估算仅供记录参考。",
        )


def test_image_bytes_are_sent_to_vision_provider() -> None:
    response = Orchestrator(ai_provider=FakeVisionProvider()).run(
        OrchestrateInput(
            session_id="meal-session",
            text="帮我看看这顿饭",
            has_image=True,
            has_document=False,
            mode="auto",
            attachment_name="meal.png",
            attachment_content_type="image/png",
            attachment_bytes=b"valid-image",
        )
    )

    module = response.module_plan[0]
    assert module.type == "MealAnalyzer"
    assert module.status == "ready"
    assert module.props["items"][0]["name"] == "米饭"
    assert module.props["total_calories"] == [180, 240]
    assert module.props["total_calories_center"] == 210
    assert module.props["items"][0]["portion_grams"] == [150, 180]
    assert module.props["status"] == "ready"


def test_unconfigured_vision_never_returns_a_savable_zero_result() -> None:
    response = Orchestrator(ai_provider=None).run(
        OrchestrateInput(
            session_id="meal-session",
            text=None,
            has_image=True,
            has_document=False,
            mode="auto",
            attachment_content_type="image/png",
            attachment_bytes=b"valid-image",
        )
    )

    module = response.module_plan[0]
    assert module.status == "error"
    assert module.props["status"] == "error"
    assert module.props["items"] == []
    assert "analysis_error" in module.props
