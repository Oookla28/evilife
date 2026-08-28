"""Claim worthiness: decide whether a fragment is a testable health claim.

Rules-first and deterministic. A claim must be falsifiable (has an
evaluative predicate) and health-related to be worth an evidence chain.
Pure commands, greetings, and fragments without a predicate are dropped.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

# Evaluative predicates that make a fragment a testable proposition.
_EVALUATIVE = re.compile(
    r"降低|升高|增加|减少|改善|缓解|减轻|预防|帮助|有效|无效|导致|引起|"
    r"影响|风险|有益|有害|促进|抑制|治愈|根治|加速|延缓|优于|"
    r"比\S{0,4}(更|还|都)|可以|能|能够|会|有助于|"
    r"不会|不能|不容易|不\S{0,2}(增加|减少|影响|导致|掉|损伤)|"
    r"无益|无效|好处|益处|效果|提神|有助于降"
)
# Health domains that mark a fragment as health-related.
_HEALTH_DOMAIN = re.compile(
    r"血压|血糖|血脂|体重|肥胖|减肥|减重|心血管|心脏|脑|中风|卒中|"
    r"睡眠|失眠|运动|锻炼|饮食|营养|维生素|蛋白质|碳水|脂肪|热量|卡路里|"
    r"盐|钠|糖|咖啡|茶|饮酒|酒精|吸烟|代谢|胰岛素|胆固醇|"
    r"癌症|肿瘤|糖尿病|高血压|肾病|肝脏|免疫|骨|肌肉|寿命|衰老|"
    r"健康|疾病|症状|药|处方|剂量|医生|医院|就医"
)
# Pure feature commands that must not be treated as claims.
_COMMAND = re.compile(
    r"^(打开|开始|查看|显示|关闭|暂停|跳过|导入|连接|设置|记录|"
    r"帮我(记录|设置|打开|导入))|计时|今日记录"
)


class ClaimWorthiness(BaseModel):
    is_claim: bool
    reason: str
    claim_type_hint: str | None = None


def assess(fragment: str) -> ClaimWorthiness:
    """Deterministic worthiness check for one sentence fragment."""
    text = (fragment or "").strip()
    if not text:
        return ClaimWorthiness(is_claim=False, reason="空片段")
    if len(text) < 4:
        return ClaimWorthiness(is_claim=False, reason="片段过短")
    if _COMMAND.search(text):
        return ClaimWorthiness(is_claim=False, reason="功能命令而非主张")
    if not _HEALTH_DOMAIN.search(text):
        return ClaimWorthiness(is_claim=False, reason="不含健康领域内容")
    if not _EVALUATIVE.search(text):
        return ClaimWorthiness(is_claim=False, reason="无可证伪谓语（定义/事实询问）")
    return ClaimWorthiness(is_claim=True, reason="可证伪的健康主张")


def classify(text: str) -> str:
    """Lightweight claim-type hint (best-effort, deterministic)."""
    text = (text or "").strip()
    if re.search(r"比.{0,6}(更|还|都)|优于|强于|胜过", text):
        return "comparison"
    if re.search(r"导致|引起|造成|诱发|增加.{0,6}风险", text):
        return "causal"
    if re.search(r"风险因素|危险因素|增加.{0,6}(风险|几率|概率)", text):
        return "risk_factor"
    if re.search(r"血糖|胰岛素|血脂|代谢|胆固醇", text):
        return "metabolic"
    if re.search(r"肌肉|掉肌|减脂|增肌|副作用|安全|损伤", text):
        return "safety_or_body_composition"
    if re.search(r"衰老|寿命|长寿|延缓|抗衰", text):
        return "longevity"
    if re.search(r"所有人|任何人|普遍|都适用|一定|保证|100%", text):
        return "population_claim"
    if re.search(r"有效|改善|降低|减少|帮助|预防|可以|有助于|提神|促进|有益|好处|益处", text):
        return "effectiveness"
    return "other"
