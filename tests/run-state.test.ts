import { describe, expect, it } from "vitest";
import { initialRunState, reduceRunState } from "@/lib/chat/run-state";
import type { StreamEvent } from "@/lib/api/types";

const event = (type: StreamEvent["type"], payload: Record<string, unknown> = {}): StreamEvent => ({
  event_id: `event-${type}`,
  request_id: "req-1",
  run_id: "run-1",
  type,
  timestamp: new Date(0).toISOString(),
  payload,
});

describe("reduceRunState", () => {
  it("tracks route and streamed text", () => {
    const routed = reduceRunState(initialRunState, event("route.selected", { route: "ai_fast" }));
    const streamed = reduceRunState(routed, event("answer.delta", { delta: "回答" }));
    expect(streamed).toMatchObject({ phase: "streaming", route: "ai_fast", streamedText: "回答" });
  });

  it("keeps a failed run recoverable", () => {
    const failed = reduceRunState(initialRunState, event("run.failed", { message: "超时" }));
    expect(failed).toMatchObject({ phase: "failed", error: "超时" });
  });
});
