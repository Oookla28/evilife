"""Deterministic ethics boundary for non-medical, general-purpose answers.

The health evidence gate decides whether a question belongs to the product's
medical scope.  This module is the second gate: it allows ordinary knowledge,
writing and learning questions, while refusing operational help that would
enable harm, crime, fraud, privacy invasion or sexual exploitation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


GeneralEthicsCategory = Literal[
    "allowed",
    "violence_or_weapons",
    "cyber_abuse",
    "fraud_or_impersonation",
    "privacy_invasion",
    "sexual_exploitation",
    "targeted_hate_or_harassment",
]


@dataclass(frozen=True, slots=True)
class GeneralEthicsDecision:
    allowed: bool
    category: GeneralEthicsCategory
    reason: str


_BLOCKING_PATTERNS: tuple[
    tuple[GeneralEthicsCategory, str, re.Pattern[str]], ...
] = (
    (
        "violence_or_weapons",
        "不能提供制作武器、爆炸物或实施人身伤害的操作方法",
        re.compile(
            r"(?:怎么|如何|教我|帮我|步骤|教程|配方|方案).{0,18}"
            r"(?:制作|制造|组装|改装|引爆|下毒|杀死|袭击|伤害).{0,12}"
            r"(?:炸弹|爆炸物|枪|武器|毒药|毒气|某人|别人|他|她)?"
            r"|(?:制作|制造|组装|改装).{0,10}(?:炸弹|爆炸物|枪支|毒气|毒药)",
            re.IGNORECASE,
        ),
    ),
    (
        "cyber_abuse",
        "不能帮助入侵账户、盗取凭据、部署恶意软件或绕过安全验证",
        re.compile(
            r"(?:怎么|如何|教我|帮我|写个|给我).{0,18}"
            r"(?:黑进|入侵|盗号|盗取|窃取|破解密码|绕过.{0,6}验证|植入木马|"
            r"勒索软件|恶意软件|偷取cookie|偷取令牌|credential\s*theft|phishing)",
            re.IGNORECASE,
        ),
    ),
    (
        "fraud_or_impersonation",
        "不能生成用于诈骗、冒充身份或骗取钱款与验证码的内容",
        re.compile(
            r"(?:帮我|替我|生成|写一段|写个|设计).{0,16}"
            r"(?:诈骗|钓鱼|冒充|骗取|套取).{0,18}"
            r"(?:钱|转账|验证码|密码|账户|身份|信任|点击链接)?"
            r"|(?:伪造|篡改).{0,10}(?:证件|公章|合同|账单|凭证)",
            re.IGNORECASE,
        ),
    ),
    (
        "privacy_invasion",
        "不能协助人肉、开盒或获取他人的敏感个人信息与实时行踪",
        re.compile(
            r"(?:怎么|如何|帮我|替我|给我).{0,16}"
            r"(?:人肉|开盒|查出|定位|跟踪|获取).{0,14}"
            r"(?:住址|身份证|手机号|电话|家庭成员|实时位置|行踪|隐私)",
            re.IGNORECASE,
        ),
    ),
    (
        "sexual_exploitation",
        "不能提供涉及未成年人或非自愿性内容的性剥削帮助",
        re.compile(
            r"(?:未成年|儿童|小孩|学生).{0,18}"
            r"(?:裸照|色情|性交易|性行为|私密照|诱骗|胁迫)"
            r"|(?:偷拍|胁迫|强迫).{0,12}(?:裸照|私密照|性行为)",
            re.IGNORECASE,
        ),
    ),
    (
        "targeted_hate_or_harassment",
        "不能生成煽动针对特定群体或个人实施暴力与持续骚扰的内容",
        re.compile(
            r"(?:帮我|写一段|生成|设计).{0,14}"
            r"(?:煽动|号召|鼓动).{0,16}(?:杀|打|伤害|驱逐|骚扰|围攻)"
            r"|(?:怎么|如何).{0,12}(?:持续骚扰|网暴|恐吓).{0,10}(?:某人|别人|他|她)",
            re.IGNORECASE,
        ),
    ),
)


class GeneralEthicsRouter:
    """Conservative, narrow gate that avoids blocking benign discussion."""

    def assess(self, text: str | None) -> GeneralEthicsDecision:
        normalized = " ".join((text or "").split())
        for category, reason, pattern in _BLOCKING_PATTERNS:
            if pattern.search(normalized):
                return GeneralEthicsDecision(
                    allowed=False,
                    category=category,
                    reason=reason,
                )
        return GeneralEthicsDecision(
            allowed=True,
            category="allowed",
            reason="普通非医学问题可在明确边界下回答",
        )
