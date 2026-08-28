from __future__ import annotations

import io
import re
from typing import Literal

from pydantic import BaseModel, Field


class ReportItem(BaseModel):
    name: str
    value: str = ""
    unit: str = ""
    reference_range: str = ""
    flag: Literal["high", "low", "normal", "unknown"] = "unknown"


class ReportAnalysis(BaseModel):
    report_id: str = ""
    file_name: str
    source: Literal["text_extraction", "deepseek_vl2", "limited_fallback"]
    summary: str
    items: list[ReportItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


_ROW = re.compile(
    r"^\s*([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9 ()/%+-]{1,40}?)\s+"
    r"([<>]?\s*-?\d+(?:\.\d+)?)\s*([a-zA-Zμµ/%^·0-9]+)?\s*"
    r"(?:([\[(]?\s*-?\d+(?:\.\d+)?\s*[-~—至]\s*-?\d+(?:\.\d+)?\s*[\])]?)|([↑↓HL]))?\s*$"
)


def extract_report_text(payload: bytes, mime_type: str, filename: str) -> str:
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(payload))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""
    if mime_type.startswith("text/") or filename.lower().endswith((".txt", ".csv")):
        return payload.decode("utf-8", errors="replace")
    return ""


def analyze_text(text: str, filename: str) -> ReportAnalysis:
    items: list[ReportItem] = []
    for line in text.splitlines():
        match = _ROW.match(line)
        if not match:
            continue
        name, value, unit, reference, marker = match.groups()
        flag: Literal["high", "low", "normal", "unknown"] = "unknown"
        if marker in {"↑", "H"}:
            flag = "high"
        elif marker in {"↓", "L"}:
            flag = "low"
        elif reference:
            flag = "normal"
        items.append(
            ReportItem(
                name=name.strip(),
                value=value.replace(" ", ""),
                unit=(unit or "").strip(),
                reference_range=(reference or "").strip(),
                flag=flag,
            )
        )
    flagged = sum(item.flag in {"high", "low"} for item in items)
    return ReportAnalysis(
        file_name=filename,
        source="text_extraction" if text.strip() else "limited_fallback",
        summary=(
            f"共结构化读取 {len(items)} 个项目，其中 {flagged} 个带有报告原文异常标记。"
            if items
            else "文件已安全接收，但没有可靠提取到结构化检验项目。"
        ),
        items=items,
        limitations=[
            "结果仅用于整理报告原文，不构成诊断或治疗建议。",
            "参考范围会因实验室、年龄、性别、孕期和检测方法而变化，请以原报告和医生解释为准。",
            "自动识别可能有误，请逐项核对数值、单位和参考范围。",
        ],
    )
