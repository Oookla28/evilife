export type MedicalCardTone = "summary" | "support" | "population" | "boundary" | "action";
export type MedicalCardIcon = "heart" | "activity" | "water" | "sleep" | "body" | "mood" | "connect" | "tcm" | "shield" | "check" | "note";

export interface MedicalEvidenceFlowSource {
  evidence_id: string;
  title: string;
  year?: number | null;
  source_type: string;
  organization?: string | null;
  direction: "support" | "against" | "mixed" | "context";
  finding: string;
  url?: string;
  channel?: "curated_database" | "live_medical_search" | null;
}

export interface MedicalFlowCard {
  id: string;
  title: string;
  tag: string;
  preview: string;
  body: string;
  tone: MedicalCardTone;
  icon?: MedicalCardIcon;
  sourceUrl?: string;
  sourceLinks?: Array<{
    label: string;
    url: string;
  }>;
  trend?: {
    label: string;
    unit: string;
    chart: "bar" | "line";
    color: string;
    points: Array<{ date: string; value: number; source?: string }>;
  };
  details: Array<{
    label: string;
    value: string;
  }>;
}

export interface MedicalAnswerSections {
  conclusion?: string;
  explanation?: string;
  supportingEvidence?: MedicalEvidenceFlowSource[];
  opposingEvidence?: MedicalEvidenceFlowSource[];
  targetPopulation?: string[];
  nonTargetPopulation?: string[];
  generalAdvice?: string[];
  limitations?: string[];
}

const clean = (value?: string) => value?.trim() ?? "";

const firstItem = (items?: string[]) =>
  (items ?? []).map((item) => item.trim()).find(Boolean) ?? "";

const joinItems = (items?: string[]) =>
  {
    const text = (items ?? [])
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => item.replace(/[。；;]+$/u, ""))
    .join("；");
    return text ? `${text}。` : "";
  };

export function buildMedicalFlowCards({
  conclusion,
  explanation,
  supportingEvidence = [],
  opposingEvidence = [],
  targetPopulation,
  nonTargetPopulation,
  generalAdvice,
  limitations,
}: MedicalAnswerSections): MedicalFlowCard[] {
  const cards: MedicalFlowCard[] = [];
  const summary = [clean(conclusion), clean(explanation)].filter(Boolean).join("\n");

  if (summary) {
    const summaryDetails = [
      { label: "核心结论", value: clean(conclusion) },
      { label: "证据说明", value: clean(explanation) },
    ].filter((item) => item.value);
    cards.push({
      id: "summary",
      title: "核心结论",
      tag: "医疗摘要",
      preview: clean(conclusion) || clean(explanation),
      body: summary,
      tone: "summary",
      details: summaryDetails,
    });
  }

  const pushEvidenceGroup = (
    items: MedicalEvidenceFlowSource[],
    tone: "support" | "boundary"
  ) => {
    if (!items.length) return;
    const isSupport = tone === "support";
    const directionLabel = isSupport ? "支持证据" : "反对 / 边界证据";
    const findings = items.map((item) => clean(item.finding)).filter(Boolean);
    cards.push({
      id: isSupport ? "supporting-evidence" : "opposing-evidence",
      title: `${directionLabel} · ${items.length} 条`,
      tag: directionLabel,
      preview: `${items.length} 条研究已合并整理。${findings[0] ?? "翻面查看完整证据。"}`,
      body: findings.join("\n"),
      tone,
      icon: isSupport ? "check" : "shield",
      sourceLinks: items.flatMap((item, index) =>
        item.url ? [{ label: `${index + 1}. ${item.title || directionLabel}`, url: item.url }] : []
      ),
      details: items.map((item, index) => {
        const source = [item.organization, item.year].filter(Boolean).join(" · ");
        const channel = item.channel === "live_medical_search" ? "实时检索" : "人工核验/证据库";
        return {
          label: `证据 ${index + 1}`,
          value: [
            item.title,
            item.finding,
            [source || "来源信息未提供", item.source_type || "未标注", channel].join(" · "),
          ].filter(Boolean).join("\n"),
        };
      }),
    });
  };

  pushEvidenceGroup(supportingEvidence, "support");
  pushEvidenceGroup(opposingEvidence, "boundary");

  const population = joinItems(targetPopulation);
  if (population) {
    cards.push({
      id: "population",
      title: "适用人群与场景",
      tag: "适用范围",
      preview: firstItem(targetPopulation),
      body: population,
      tone: "population",
      details: [{ label: "适用人群", value: population }],
    });
  }

  const boundary = [joinItems(nonTargetPopulation), joinItems(limitations)]
    .filter(Boolean)
    .join("\n");
  if (boundary) {
    cards.push({
      id: "boundary",
      title: "证据边界与局限",
      tag: "谨慎解读",
      preview: firstItem(nonTargetPopulation) || firstItem(limitations),
      body: boundary,
      tone: "boundary",
      details: [
        { label: "不适用或不能推断", value: joinItems(nonTargetPopulation) },
        { label: "证据局限", value: joinItems(limitations) },
      ].filter((item) => item.value),
    });
  }

  const advice = joinItems(generalAdvice);
  if (advice) {
    cards.push({
      id: "action",
      title: "一般性行动建议",
      tag: "安全建议",
      preview: firstItem(generalAdvice),
      body: advice,
      tone: "action",
      details: [{ label: "可执行建议", value: advice }],
    });
  }

  return cards;
}
