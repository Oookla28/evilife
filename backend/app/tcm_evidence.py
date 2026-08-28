"""Conservative TCM-reference lookup for a secondary, non-diagnostic card.

The catalogue separates terminology/knowledge bases from clinical-effect
evidence. Database presence must never be presented as proof of efficacy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

@dataclass(frozen=True, slots=True)
class TCMSource:
    source_id: str
    title: str
    organization: str
    url: str
    role: str


TCM_DATABASES = (
    TCMSource(
        "TCM-WHO-TERMS",
        "WHO international standard terminologies on traditional Chinese medicine",
        "World Health Organization",
        "https://www.who.int/publications/b/55892",
        "规范中医术语；不用于证明疗效",
    ),
    TCMSource(
        "TCM-SINOMED",
        "中国生物医学文献服务系统 SinoMed",
        "中国医学科学院医学信息研究所/图书馆",
        "https://www.sinomed.ac.cn/index.jsp",
        "检索中文生物医学与中医药文献线索",
    ),
    TCMSource(
        "TCM-ETCM2",
        "ETCM v2.0 中药百科数据库",
        "ETCM v2.0 研究团队",
        "https://pubmed.ncbi.nlm.nih.gov/37425046/",
        "核对方剂、中药材与成分关系；不等同临床有效",
    ),
)


def _questions(question: str) -> list[str]:
    common = ["症状在什么时间、环境或饮食后更明显？", "是否伴随怕冷或怕热、口渴、食欲和排便变化？"]
    if any(word in question for word in ("睡", "失眠", "早醒")):
        return ["入睡困难、易醒和早醒分别持续多久？", "睡前情绪、饮食、咖啡因与作息有什么变化？", *common[:1]]
    if any(word in question for word in ("血压", "心率", "心血管", "头晕")):
        return ["不适出现时的血压、心率、睡眠和活动记录是否同步？", "是否伴胸痛、呼吸困难、晕厥等需要优先就医的信号？", *common[:1]]
    if any(word in question for word in ("饮食", "胃", "腹", "减肥", "体重")):
        return ["食欲、餐后感受、口渴和排便是否同步变化？", "冷热食物、进餐时间与不适之间是否有稳定关系？", *common[:1]]
    return common + ["舌象、脉象等信息需要由合格中医师现场综合判断。"]


def _topic_fallback(question: str) -> tuple[str, list[str]]:
    compact = "".join(question.split())
    if any(word in compact for word in ("睡", "失眠", "早醒")):
        return (
            "针对你问的睡眠问题，中医视角只能补充观察入睡、夜醒、早醒与情绪、饮食和作息的同步变化，不能据一句描述判定证型。",
            ["把睡眠节律与白天精神、情绪和晚餐时间放在同一时间线上观察。"],
        )
    if any(word in compact for word in ("血压", "心率", "心血管", "头晕")):
        return (
            "针对你问的心血管相关问题，中医视角仅补充症状节律与睡眠、情绪、活动的记录，治疗和风险判断仍以临床证据为准。",
            ["把不适发生时的血压、心率、活动和睡眠记录对齐，优先排查需要及时就医的信号。"],
        )
    if any(word in compact for word in ("饮食", "胃", "腹", "减肥", "体重")):
        return (
            "针对你问的饮食或体重问题，中医视角可补充观察食欲、餐后感受、口渴和排便，但不能替代营养与临床证据。",
            ["观察进餐时间、冷热食物与不适是否存在可重复关系，而不是直接归入某个证型。"],
        )
    topic = compact[:36] or "当前健康问题"
    return (
        f"针对“{topic}”，中医视角只能作为补充观察框架；现有信息不足以确定证型或治疗方案。",
        ["记录症状时间、诱因、睡眠、饮食和情绪的同步变化，再交由合格专业人员综合判断。"],
    )


def _sources(evidence_props: dict) -> list[dict]:
    clinical: list[dict] = []
    # Keep the compact, highest-ranked evidence set. The main answer may expose
    # more exploratory search hits, but the TCM card should not amplify noisy,
    # weakly related literature merely because it appeared later in retrieval.
    for item in (evidence_props.get("citations") or [])[:3]:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        clinical.append(
            {
                "source_id": str(item.get("source_id") or item.get("evidence_id") or "clinical-source"),
                "title": title,
                "organization": str(item.get("organization") or "临床文献来源"),
                "year": item.get("year"),
                "url": str(item.get("url") or ""),
                "role": "约束主问题的临床疗效、安全与适用边界",
                "source_type": str(item.get("source_type") or "clinical_evidence"),
            }
        )
    return [*clinical, *(asdict(source) for source in TCM_DATABASES)]


def build_tcm_perspective(question: str, evidence_props: dict) -> dict:
    mix = evidence_props.get("evidence_mix") or {}
    reliable = float(mix.get("reliable_weight", 0.0) or 0.0)
    general = float(mix.get("general_weight", 1.0) or 1.0)
    topic_link, perspective = _topic_fallback(question)
    summary = (
        f"{topic_link} 主回答现有证据是判断疗效和安全的基础；中医部分只补充观察维度。"
    )
    return {
            "title": "中医视角：补充观察思路",
            "summary": summary,
            "topic_link": topic_link,
            "perspective": perspective,
            "questions": _questions(question),
            "safe_ideas": [
                "把症状、饮食、睡眠和情绪按时间连续记录，寻找可重复的触发关系。",
                "优先采用规律作息、适量活动和均衡饮食等低风险生活方式。",
            ],
            "avoid": "不根据网页结果自行开方、停药、针灸或服用中药；中药同样可能有不良反应和药物相互作用。",
            "evidence_note": (
                f"沿用主回答的证据策略：{reliable:.0%} 可追溯临床证据 + {general:.0%} 一般语境。"
                "中医数据库只提供术语、文献与药材关系线索，疗效和安全结论仍以主卡的临床证据为准。"
            ),
            "limitations": [
                "现有对话不含完整病史、体格检查、舌脉等现场信息，不能据此辨证或诊断。",
                "中医数据库的收录与关联不代表临床疗效或安全性已经得到证实。",
            ],
            "ai_summary": summary,
            "sources": _sources(evidence_props),
            "source": "deterministic_fallback",
            "gate_status": "degraded" if reliable < 0.75 else "normal",
    }
