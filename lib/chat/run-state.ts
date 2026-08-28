import type { StreamEvent } from "@/lib/api/types";

export type RunPhase =
  | "idle"
  | "starting"
  | "routing"
  | "collecting"
  | "streaming"
  | "ready"
  | "stopped"
  | "failed";

export interface RunState {
  phase: RunPhase;
  route?: string;
  streamedText: string;
  error?: string;
}

export const initialRunState: RunState = {
  phase: "idle",
  streamedText: "",
};

const payloadString = (event: StreamEvent, key: string) => {
  const value = event.payload?.[key];
  return typeof value === "string" ? value : undefined;
};

export const reduceRunState = (state: RunState, event: StreamEvent): RunState => {
  switch (event.type) {
    case "run.started":
      return { ...state, phase: "starting" };
    case "route.selected":
      return { ...state, phase: "routing", route: payloadString(event, "route") };
    case "evidence.snapshot":
      return { ...state, phase: "collecting" };
    case "answer.delta":
      return {
        ...state,
        phase: "streaming",
        streamedText:
          state.streamedText +
          (payloadString(event, "delta") ?? payloadString(event, "text") ?? ""),
      };
    case "module.ready":
    case "gate.completed":
      return { ...state, phase: "ready" };
    case "run.completed":
      return { ...state, phase: "ready" };
    case "run.failed":
      return {
        ...state,
        phase: "failed",
        error: payloadString(event, "message") ?? "生成失败，请重试。",
      };
    default:
      return state;
  }
};

export const runPhaseLabel: Record<RunPhase, string> = {
  idle: "等待开始",
  starting: "咱们先把问题捋一遍",
  routing: "正在挑合适的分析路径",
  collecting: "正在把证据一条条对上",
  streaming: "正在把结论讲清楚",
  ready: "这轮回答整理好了",
  stopped: "已停止生成",
  failed: "这次没跑通",
};
