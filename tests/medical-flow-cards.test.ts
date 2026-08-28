import { describe, expect, it } from "vitest";
import { buildMedicalFlowCards } from "@/lib/evidence/build-medical-flow-cards";

describe("buildMedicalFlowCards", () => {
  it("按医疗语义生成完整的中文卡片序列", () => {
    const cards = buildMedicalFlowCards({
      conclusion: "减少钠摄入有助于降低血压。",
      explanation: "高血压人群的平均降压幅度更明显。",
      targetPopulation: ["需要控制血压的成年人"],
      nonTargetPopulation: ["不能替代降压药"],
      limitations: ["个体反应存在差异"],
      generalAdvice: ["比较食品标签中的钠含量"],
    });

    expect(cards.map((card) => card.id)).toEqual([
      "summary",
      "population",
      "boundary",
      "action",
    ]);
    expect(cards.every((card) => /[\u3400-\u9fff]/u.test(card.body))).toBe(true);
    expect(cards.every((card) => /[\u3400-\u9fff]/u.test(card.preview))).toBe(true);
    expect(cards.every((card) => card.details.length > 0)).toBe(true);
    expect(cards[0].details.map((item) => item.label)).toEqual([
      "核心结论",
      "证据说明",
    ]);
  });

  it("不会为缺失内容生成空卡片", () => {
    const cards = buildMedicalFlowCards({ conclusion: "这是中文结论。" });
    expect(cards).toHaveLength(1);
    expect(cards[0].id).toBe("summary");
  });

  it("把全部支持与反对证据分别合并成一张 Flow 卡并保留原文入口", () => {
    const cards = buildMedicalFlowCards({
      conclusion: "地中海饮食可能降低部分人群的心血管风险。",
      supportingEvidence: [
        {
          evidence_id: "S1",
          title: "随机对照试验",
          year: 2018,
          source_type: "随机对照试验",
          organization: "PREDIMED 研究团队",
          direction: "support",
          finding: "主要心血管事件风险较低。",
          url: "https://example.org/support",
          channel: "curated_database",
        },
        {
          evidence_id: "S2",
          title: "队列研究",
          year: 2020,
          source_type: "队列研究",
          organization: "研究团队 B",
          direction: "support",
          finding: "整体饮食模式与较低风险相关。",
          url: "https://example.org/support-2",
          channel: "live_medical_search",
        },
      ],
      opposingEvidence: [
        {
          evidence_id: "B1",
          title: "系统综述",
          year: 2019,
          source_type: "系统综述",
          organization: "Cochrane",
          direction: "against",
          finding: "部分结局证据质量较低。",
          url: "https://example.org/boundary",
          channel: "live_medical_search",
        },
      ],
      targetPopulation: ["心血管高风险成年人"],
      nonTargetPopulation: ["不能推断每个人获益相同"],
    });

    expect(cards.map((card) => card.id)).toEqual([
      "summary",
      "supporting-evidence",
      "opposing-evidence",
      "population",
      "boundary",
    ]);
    expect(cards[1]).toMatchObject({
      tone: "support",
      tag: "支持证据",
      title: "支持证据 · 2 条",
    });
    expect(cards[2]).toMatchObject({
      tone: "boundary",
      tag: "反对 / 边界证据",
    });
    expect(cards[1].details).toHaveLength(2);
    expect(cards[1].sourceLinks).toHaveLength(2);
    expect(cards[1].sourceLinks?.[0].url).toBe("https://example.org/support");
    expect(cards[2].details).toHaveLength(1);
    expect(cards[2].sourceLinks?.[0].url).toBe("https://example.org/boundary");
  });
});
