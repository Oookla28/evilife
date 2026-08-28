import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RunStatus } from "@/components/chat/RunStatus";

describe("RunStatus", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("shows an auditable progress summary without claiming hidden reasoning", () => {
    render(<RunStatus state={{ phase: "starting", streamedText: "" }} />);

    expect(screen.getByText("可审计处理过程")).toBeInTheDocument();
    expect(screen.getByText("读懂问题与安全边界")).toBeInTheDocument();
    expect(screen.getByText(/不展示模型隐藏的逐字思维链/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "回答处理进度" })).toHaveAttribute("aria-valuenow", "12");
  });

  it("advances the top progress bar while processing continues", () => {
    vi.useFakeTimers();
    render(<RunStatus state={{ phase: "starting", streamedText: "" }} />);

    act(() => vi.advanceTimersByTime(3600));

    expect(screen.getByRole("progressbar", { name: "回答处理进度" })).toHaveAttribute("aria-valuenow", "58");
    expect(screen.getByText("58%")).toBeInTheDocument();
  });
});
