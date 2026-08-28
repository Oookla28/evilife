"""Map explicit chat commands to already implemented product modules."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureIntent:
    name: str
    module_type: str
    title: str


FEATURES: tuple[tuple[re.Pattern[str], FeatureIntent], ...] = (
    (
        re.compile(r"综合(?:健康|身体)分析|分析(?:一下)?我的(?:身体|健康|健康档案)|AI健康分析|身体状况"),
        FeatureIntent("health_profile_analysis", "ChatFeaturePanel", "综合健康分析"),
    ),
    (
        re.compile(
            r"(?:开始|打开|设置|启用|使用|继续|结束|停止|记录)"
            r".{0,8}(?:轻断食|断食|进食窗口|进食间隔|16\s*[:：]\s*8)"
            r"(?:.{0,6}(?:计时器?|记录))?"
            r"|(?:轻断食|断食|进食窗口|进食间隔|16\s*[:：]\s*8)"
            r".{0,8}(?:计时器?|开始记录|打开|设置|启用|结束|停止)"
        ),
        FeatureIntent("fasting_timer", "FastingTimer", "进食间隔计时"),
    ),
    (
        re.compile(r"今日(?:记录|回顾|汇总)|今天(?:记录|吃了什么|的数据|的健康记录)"),
        FeatureIntent("today_review", "ChatFeaturePanel", "今日记录"),
    ),
    (
        re.compile(r"导入.{0,8}(?:Apple|苹果)(?:健康)?|(?:Apple|苹果)健康.{0,8}(?:导入|数据)" , re.I),
        FeatureIntent("apple_health_import", "ChatFeaturePanel", "导入 Apple 健康"),
    ),
    (
        re.compile(r"连接.{0,8}(?:健康软件|Apple|苹果|华为|Health\s*Connect)|健康软件.{0,8}(?:连接|同步)", re.I),
        FeatureIntent("health_connectors", "ChatFeaturePanel", "连接健康软件"),
    ),
    (
        re.compile(
            r"(?:打开|使用|开始|我要|帮我).{0,10}(?:拍照|图片|照片)"
            r".{0,10}(?:热量|卡路里|餐食|食物|识别|估算)"
            r"|(?:拍照|图片|照片).{0,8}(?:识别|估算).{0,6}(?:功能|工具|入口)"
        ),
        FeatureIntent("meal_photo", "ChatFeaturePanel", "餐食图片识别"),
    ),
)


def extract_feature_intents(text: str | None) -> list[FeatureIntent]:
    if not text:
        return []
    found: list[FeatureIntent] = []
    for pattern, feature in FEATURES:
        if pattern.search(text) and all(item.name != feature.name for item in found):
            found.append(feature)
    return found


def is_pure_feature_command(text: str | None, intents: list[FeatureIntent]) -> bool:
    if not text or not intents:
        return False
    # 健康评估/比较/疑问类标记：命中即视为健康问题而非功能命令，
    # 避免“16:8 一定比普通控制热量更有效”这类问题被计时器路由吞掉。
    medical_question_markers = re.compile(
        r"为什么|原因|症状|疼|痛|头晕|发热|咳|药|治疗|疾病|是否|能不能|"
        r"怎么办|正常吗|风险|有效|效果|证据|帮助|减肥|减重|控制体重|"
        r"血糖|血压|血脂|一定|更有效|更好|更健康|比较|对比|是不是|"
        r"好处|影响|作用|预防|吗(?:呢|啊)?$"
    )
    return not medical_question_markers.search(text)
