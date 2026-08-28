import { describe, expect, it } from "vitest";
import { adaptModule } from "@/lib/api/adapters";

describe("adaptModule", () => {
  it("normalizes backend evidence citations", () => {
    const adapted = adaptModule({
      module_id: "m1",
      type: "EvidenceAnswer",
      status: "ready",
      props: {
        evidence_strength: "high",
        citations: [
          {
            evidence_id: "E1",
            source_id: "who-sodium",
            title: "WHO sodium guideline",
            organization: "WHO",
            year: 2023,
            url: "https://example.test/who",
          },
        ],
      },
    });

    expect(adapted.props.citations).toEqual([
      expect.objectContaining({ id: "E1", title: "WHO sodium guideline", organization: "WHO" }),
    ]);
  });

  it("normalizes legacy mock fields", () => {
    const adapted = adaptModule({
      module_id: "m2",
      type: "EvidenceAnswer",
      status: "ready",
      props: { strength: "High", target_audience: "成年人", sources: [{ title: "Study" }] },
    });
    expect(adapted.props.evidence_strength).toBe("high");
    expect(adapted.props.target_population).toEqual(["成年人"]);
  });
});
