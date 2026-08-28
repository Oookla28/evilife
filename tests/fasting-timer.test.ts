import { describe, expect, it } from "vitest";
import { formatElapsed } from "@/components/lifestyle/FastingTimer";

describe("fasting timer formatting", () => {
  it("formats objective elapsed time without health inference", () => {
    expect(formatElapsed(0)).toBe("00:00:00");
    expect(formatElapsed(3_661_000)).toBe("01:01:01");
  });
});
