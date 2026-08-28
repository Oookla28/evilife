from __future__ import annotations


UNKNOWN_TOPIC = "unknown"


class TopicMatcher:
    """Match only when the packet's defining intervention is explicit.

    Outcomes such as “心血管” or diagnoses such as “高血压” are deliberately
    not sufficient: otherwise egg/coffee/exercise questions are silently
    routed to an unrelated diet packet.
    """

    _RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
        (
            "sodium_and_hypertension",
            (
                "限钠", "限盐", "低钠", "低盐", "少盐", "减少钠",
                "钠摄入", "食盐摄入",
            ),
            (),
        ),
        (
            "mediterranean_diet_and_cardiovascular_risk",
            ("地中海饮食", "地中海膳食"),
            (),
        ),
        (
            "time_restricted_eating_and_weight",
            ("限时进食", "16:8", "间歇性禁食", "间歇性断食"),
            (),
        ),
        (
            "coffee_and_blood_pressure",
            ("咖啡",),
            (),
        ),
        (
            "egg_consumption_and_cardiovascular_risk",
            ("鸡蛋", "蛋类"),
            ("心血管", "心脏", "卒中", "中风"),
        ),
        (
            "exercise_and_sleep_quality",
            ("运动", "锻炼"),
            ("睡眠", "失眠"),
        ),
    )

    def match(self, question: str | None) -> str:
        normalized = (question or "").strip().lower()
        if not normalized:
            return UNKNOWN_TOPIC

        for topic, keywords, companions in self._RULES:
            if any(keyword in normalized for keyword in keywords) and (
                not companions
                or any(companion in normalized for companion in companions)
            ):
                return topic
        return UNKNOWN_TOPIC
