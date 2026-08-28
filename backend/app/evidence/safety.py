from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..schemas import EvidencePacket, GateStatus


SafetyCategory = Literal[
    "safe",
    "diagnosis",
    "medication_change",
    "medication_dosage",
    "high_risk_personal_advice",
    "population_boundary",
    "evidence_boundary",
    "limited_evidence",
    "unauthorized_clinical_override",
    "self_harm_concern",
    "self_harm_imminent",
]


class SafetyAssessment(BaseModel):
    """Deterministic safety result produced before topic routing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_status: GateStatus
    risk_level: Literal["low", "medium", "high"]
    category: SafetyCategory
    reason: str
    crisis_level: Literal["concern", "imminent"] | None = None


class SafetyRouter:
    """Rule-first safety routing; it never calls a model or guesses intent."""

    _MEDICATION_CHANGE = re.compile(
        r"停药|停用|断药|不吃药|不用药|换药|改药|减药|加药|"
        r"只吃低盐|只靠低盐|只靠饮食|替代(?:降压|心血管)?药|"
        r"(?:换|替换|改)成(?:别的|其他|别的药)?(?:药|药物|保健品|补剂|偏方)|"
        r"(?:换成|改用|替换成)\S{0,6}(?:药|保健品|补剂)"
    )
    _MEDICATION_DOSAGE = re.compile(
        r"药物?剂量|用药量|用量|吃几(?:粒|片|颗)|吃多少药|"
        r"(?:这个|这种|该|此)?药.{0,8}(?:多大|多少|怎样的?)剂量|"
        r"多少\s*(?:mg|毫克)|一天(?:吃|服)几次|怎么服用|如何服药|"
        r"药.{0,8}(?:每天|一天|多久)?(?:吃|服)(?:几|多少)次|"
        r"多久(?:吃|服)(?:一次|几次)|什么时候(?:吃|服)药",
        re.IGNORECASE,
    )
    # 治疗性声明：宣称“根治/治愈/根除”某种疾病属于治疗背书，直接拒绝。
    _TREATMENT_CURE = re.compile(
        r"(?:根治|治愈|根除|彻底治好|断根|痊愈)\s*(?:了|好)?\s*"
        r"(?:高血压|糖尿病|癌症|肿瘤|心脏病|肾病|疾病|病|症)\S{0,4}"
    )
    _DIAGNOSIS = re.compile(
        r"帮我诊断|给我诊断|判断我|我是不是(?:得了|患有|有)|"
        r"我得了什么病|这些症状是什么病|"
        r"根据.{0,12}症状.{0,8}(?:诊断|判断)|"
        r"能否确诊|可以确诊"
    )
    _HIGH_RISK = re.compile(
        r"胸痛|呼吸困难|喘不上气|昏厥|意识不清|大量出血|"
        r"疑似心梗|疑似中风|严重过敏|过敏性休克|抽搐|服毒|"
        r"过量服药|"
        r"血压\s*(?:1[89]\d|2\d\d)(?:\s*[/／]\s*\d{2,3})?"
    )
    _PERSONAL_OR_URGENT = re.compile(
        r"我|本人|现在|正在|刚刚|怎么办|该怎么办|应该怎么|需要怎么"
    )
    _SELF_HARM_DIRECT = re.compile(
        r"自杀|自残|自伤|自虐|割腕|割自己|伤害自己|杀了自己|"
        r"结束(?:自己|生命)|不想活|不想再活|活不下去|死了算了|"
        r"一了百了|从这个世界消失|永远睡过去|没有活着的必要|"
        r"想死|寻死|轻生|想消失|不想醒来|撑不下去|撑不住了|惩罚自己"
    )
    _SELF_HARM_INDIRECT = re.compile(
        r"告别所有人|最后一条消息|把东西都送人|"
        r"大家没有我会更好|我是累赘|我不值得活|"
        r"如果我不在了|以后见不到我"
    )
    _SELF_HARM_STRONG_DISTRESS = re.compile(
        r"我(?:现在|最近|一直|真的|总是|越来越|已经|有点|很|太|好像|"
        r"常常|每天|有时|偶尔)?(?:觉得|感觉)?(?:自己)?"
        r"(?:活着.{0,4}(?:没意思|没(?:有)?意义)|看不到希望|没有希望|很绝望|"
        r"生无可恋|是(?:个)?累赘|是(?:个)?负担|没有人会在乎)|"
        r"我(?:现在|最近|一直|真的|总是|越来越|已经|有点|很|太)?"
        r"(?:觉得|感觉|认为)自己.{0,6}(?:累赘|负担|没用|多余|不值得活)|"
        r"我不知道(?:自己)?还能撑多久|我不想拖累(?:任何人|家人|别人|大家)"
    )
    _SELF_HARM_EUPHEMISTIC = re.compile(
        r"长眠|永远睡(?:着|去|过去)|睡过去(?:再也)?不醒|一觉不醒|"
        r"不再醒来|结束这一切|结束痛苦|彻底解脱|从此消失|永远消失"
    )
    _SELF_HARM_METHOD_SEEKING = re.compile(
        r"怎么(?:才能|可以|做)|如何(?:才能|可以)?|有什么(?:办法|方法)|"
        r"哪种(?:办法|方法)|教我|告诉我(?:办法|方法)|怎样(?:才能|可以)"
    )
    _SELF_HARM_IMMINENT = re.compile(
        r"现在|马上|立刻|今晚|今天|正在|已经|准备|打算|计划|"
        r"方法|工具|地点|遗书|告别|药已经|站在|楼顶|桥上|刀在|绳子"
    )
    _SELF_HARM_PERSON = re.compile(
        r"我|自己|本人|朋友|同学|室友|家人|孩子|他|她|对方|有人|"
        r"怎么办|救救我"
    )
    _SELF_HARM_LIVED = re.compile(
        r"我(?:现在|最近|今晚|今天|已经|有点|总是|一直|真的|也)?"
        r"(?:很|好)?(?:不想活|活不下去|想死|自杀|自残|自伤|伤害自己|"
        r"轻生|想消失|不想醒来|撑不下去|撑不住了|惩罚自己)|"
        r"我(?:朋友|同学|室友|家人|孩子)|"
        r"(?:他|她|对方|有人).{0,10}(?:想死|自杀|自残|自伤|轻生)"
    )
    _SELF_HARM_INFORMATIONAL = re.compile(
        r"新闻|论文|研究|统计|定义|什么是|科普|如何识别|怎么帮助|"
        r"预防自杀|预防自残|心理学|社会现象|影视|小说|报道|政策|伦理|"
        r"是什么意思|词语|成语|文学|比喻|隐喻"
    )
    _POPULATION_BOUNDARY = re.compile(
        r"孕妇|怀孕|哺乳|婴儿|未成年人|肾病|肾功能|透析|"
        r"心力衰竭|心衰|进食障碍|低体重|术后|心梗后|中风后|"
        r"二级预防|继发预防|已经患有心血管|确诊过心血管"
    )
    _EVIDENCE_BOUNDARY = re.compile(
        r"所有人|任何人|一定|保证|百分之百|完全可以|绝对|"
        r"低风险人群|能活多久|死亡率一定|包治|根治"
    )
    # Ethics boundaries: identity spoofing and prescription review requests
    # cannot unlock medical decisions. These fire only when combined with
    # medication / dose / diagnosis language so ordinary questions like
    # "我是医生，想了解限钠证据" stay unblocked.
    _PSEUDO_AUTHORITY = re.compile(
        r"(我是(一名|位)?(医生|执业医师|临床医生|营养师|药剂师|"
        r"专家|教授|主任医师))|(患者|病人|本人)(已|已经)?"
        r"(授权|允许|同意|委托)(你|系统|助手)|(授权|允许|委托)"
        r"(你|系统|助手)(直接|给出|告诉我|回答)|i\s*am\s*"
        r"(a|an)?\s*(doctor|physician|nutritionist)",
        re.IGNORECASE,
    )
    _PRESCRIPTION_REVIEW = re.compile(
        r"帮我看(下|看|一下)?\s*(这个|这张|这)?\s*"
        r"(处方|药方|用药方案|治疗方案|剂量|用药|检查报告)"
        r"(对不对|合不合理|有没有问题|是否安全|是否合适|怎么用)?"
    )
    _DOCTOR_MEDICATION = re.compile(
        r"(医生|主治医生|大夫|医师|营养师)"
        r"(让我|叫我|要求我|给我|给我开|让我吃|让我用|让我停|让我调整)"
        r".{0,10}(药|剂量|处方|方案|停药|用药)"
    )
    _THIRD_PARTY_MEDICATION = re.compile(
        r"(我朋友|帮朋友|替朋友|为别人|我家人|我亲戚)"
        r"\s*(吃了|用了|在吃|在用|得了|确诊|医生给)"
        r"\s*(这个|这种|那)?\s*(药|药方|处方|剂量|方案|用药)"
    )

    def assess(self, question: str | None) -> SafetyAssessment:
        normalized = (question or "").strip()

        self_harm = self._assess_self_harm(normalized)
        if self_harm is not None:
            return self_harm

        if self._MEDICATION_CHANGE.search(normalized):
            return self._refused(
                "medication_change",
                "请求涉及自行停药、改药或用饮食替代处方治疗。",
            )
        if self._TREATMENT_CURE.search(normalized):
            return self._refused(
                "unauthorized_clinical_override",
                "声称可以根治或治愈疾病属于治疗性声明，系统不能背书。",
            )
        if self._MEDICATION_DOSAGE.search(normalized):
            return self._refused(
                "medication_dosage",
                "请求涉及个体化药物剂量或服药方案。",
            )
        if self._DIAGNOSIS.search(normalized):
            return self._refused(
                "diagnosis",
                "请求要求系统进行疾病诊断或确诊判断。",
            )
        if self._PRESCRIPTION_REVIEW.search(normalized):
            return self._refused(
                "unauthorized_clinical_override",
                "请求要求系统审核个人处方、用药方案或剂量。",
            )
        if self._DOCTOR_MEDICATION.search(normalized):
            return self._refused(
                "unauthorized_clinical_override",
                "转述医生处方或用药安排属于个体化医疗决策，系统不能代裁。",
            )
        if self._THIRD_PARTY_MEDICATION.search(normalized):
            return self._refused(
                "unauthorized_clinical_override",
                "第三方用药或处方信息涉及个体化治疗，系统无法安全评估。",
            )
        if self._PSEUDO_AUTHORITY.search(normalized) and (
            self._MEDICATION_CHANGE.search(normalized)
            or self._MEDICATION_DOSAGE.search(normalized)
            or self._DIAGNOSIS.search(normalized)
            or self._PRESCRIPTION_REVIEW.search(normalized)
            or re.search(r"停药|开药|开处方|剂量|确诊", normalized)
        ):
            return self._refused(
                "unauthorized_clinical_override",
                "自称医生或患者授权不能解除医疗决策边界。",
            )
        if self._HIGH_RISK.search(normalized) and self._PERSONAL_OR_URGENT.search(
            normalized
        ):
            return self._refused(
                "high_risk_personal_advice",
                (
                    "请求包含可能需要及时线下评估的高风险个人医疗"
                    "情境。"
                ),
            )
        if self._POPULATION_BOUNDARY.search(normalized):
            return SafetyAssessment(
                gate_status="degraded",
                risk_level="medium",
                category="population_boundary",
                reason=(
                    "问题涉及黄金 Evidence Packet 未充分覆盖的特殊人群"
                    "或二级预防人群。"
                ),
            )
        if self._EVIDENCE_BOUNDARY.search(normalized):
            return SafetyAssessment(
                gate_status="degraded",
                risk_level="medium",
                category="evidence_boundary",
                reason=(
                    "问题要求绝对化或超出当前 Evidence Packet 边界的"
                    "结论。"
                ),
            )
        return SafetyAssessment(
            gate_status="normal",
            risk_level="low",
            category="safe",
            reason="未命中基础医疗安全或证据边界规则。",
        )

    @classmethod
    def _assess_self_harm(cls, text: str) -> SafetyAssessment | None:
        if not text:
            return None
        direct = cls._SELF_HARM_DIRECT.search(text)
        indirect = cls._SELF_HARM_INDIRECT.search(text)
        strong_distress = cls._SELF_HARM_STRONG_DISTRESS.search(text)
        euphemistic = cls._SELF_HARM_EUPHEMISTIC.search(text)
        if not direct and not indirect and not strong_distress and not euphemistic:
            return None
        if (
            cls._SELF_HARM_INFORMATIONAL.search(text)
            and not cls._SELF_HARM_LIVED.search(text)
            and not strong_distress
            and not cls._SELF_HARM_METHOD_SEEKING.search(text)
        ):
            return None
        # Common figurative phrases are not enough on their own.
        if re.fullmatch(r"\s*(?:笑死|累死|困死|饿死|气死|烦死)(?:我了)?[。！!？?]*\s*", text):
            return None
        if (
            not cls._SELF_HARM_PERSON.search(text)
            and not indirect
            and not strong_distress
            and not euphemistic
        ):
            return None
        imminent = bool(
            cls._SELF_HARM_IMMINENT.search(text)
            or (
                euphemistic
                and cls._SELF_HARM_METHOD_SEEKING.search(text)
            )
        )
        return SafetyAssessment(
            gate_status="refused",
            risk_level="high",
            category="self_harm_imminent" if imminent else "self_harm_concern",
            reason=(
                "表达中出现了可能迫在眉睫的自杀或自伤风险，需要立即转向现实中的安全支持。"
                if imminent
                else "表达中出现了可能的自杀、自伤或强烈绝望信号，需要先关心当下安全并连接现实支持。"
            ),
            crisis_level="imminent" if imminent else "concern",
        )

    @staticmethod
    def _refused(category: SafetyCategory, reason: str) -> SafetyAssessment:
        return SafetyAssessment(
            gate_status="refused",
            risk_level="high",
            category=category,
            reason=reason,
        )


class EvidenceGate:
    """Minimal deterministic normal/degraded/refused evidence gate."""

    def evaluate(
        self,
        packet: EvidencePacket,
        safety: SafetyAssessment,
    ) -> SafetyAssessment:
        if safety.gate_status != "normal":
            return safety
        if (
            packet.evidence_strength in {"low", "insufficient"}
            or packet.conflict_detected
            or packet.overall_direction in {"mixed", "insufficient"}
        ):
            return SafetyAssessment(
                gate_status="degraded",
                risk_level="medium",
                category="limited_evidence",
                reason=(
                    "Evidence Packet 的证据强度、冲突状态或总体方向"
                    "不足以支持正常回答。"
                ),
            )
        return safety
