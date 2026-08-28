import { describe, expect, it } from "vitest";
import { clampCoverFlowIndex, resolveCoverFlowSwipe } from "@/lib/motion/cover-flow-gesture";

describe("CoverFlow gestures", () => {
  it("moves to the next card when swiping left", () => {
    expect(resolveCoverFlowSwipe(-60, 0)).toBe(1);
    expect(resolveCoverFlowSwipe(-20, -400)).toBe(1);
  });

  it("moves to the previous card when swiping right", () => {
    expect(resolveCoverFlowSwipe(60, 0)).toBe(-1);
  });

  it("ignores accidental movement and clamps boundaries", () => {
    expect(resolveCoverFlowSwipe(12, 20)).toBe(0);
    expect(clampCoverFlowIndex(-1, 3)).toBe(0);
    expect(clampCoverFlowIndex(4, 3)).toBe(2);
  });
});
