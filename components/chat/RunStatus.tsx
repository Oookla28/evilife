"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Circle, CircleStop, Loader2, RotateCcw, TriangleAlert } from "lucide-react";
import type { RunState } from "@/lib/chat/run-state";
import { runPhaseLabel } from "@/lib/chat/run-state";

export function RunStatus({
  state,
  onRetry,
}: {
  state?: RunState;
  onRetry?: () => void;
}) {
  const isActive = Boolean(state && ["starting", "routing", "collecting", "streaming"].includes(state.phase));
  const [elapsedStep, setElapsedStep] = useState(0);
  useEffect(() => {
    if (!isActive) {
      setElapsedStep(0);
      return;
    }
    const timer = window.setInterval(() => {
      setElapsedStep((current) => Math.min(current + 1, 4));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [isActive]);

  if (!state || state.phase === "idle" || state.phase === "ready") return null;

  const Icon = isActive
    ? Loader2
    : state.phase === "stopped"
      ? CircleStop
      : state.phase === "failed"
        ? TriangleAlert
      : CheckCircle2;

  if (isActive) {
    const phaseFloor = { starting: 0, routing: 1, collecting: 2, streaming: 4 } as const;
    const currentStep = Math.max(elapsedStep, phaseFloor[state.phase as keyof typeof phaseFloor] ?? 0);
    const steps = [
      "读懂问题与安全边界",
      "选择医疗或通用路径",
      "检索网页、新闻或证据",
      "去重并核对来源",
      "组织中文回答",
    ];
    const progress = [12, 32, 58, 78, 92][currentStep];

    return (
      <div role="status" className="mt-2 overflow-hidden rounded-xl border border-brand/10 bg-bg-page text-xs text-text-secondary">
        <div
          role="progressbar"
          aria-label="回答处理进度"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          className="relative h-1.5 overflow-hidden bg-black/[0.055]"
        >
          <div
            className="absolute inset-0 origin-left bg-[linear-gradient(90deg,#5DA9E9_0%,#68C8BC_58%,#F5C95E_100%)] transition-transform duration-700 ease-out will-change-transform motion-reduce:transition-none"
            style={{ transform: `scaleX(${progress / 100})` }}
          >
            <span className="audit-progress-shimmer absolute inset-y-0 left-0 w-1/3 bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.78),transparent)] motion-reduce:hidden" />
          </div>
        </div>
        <div className="px-3 py-2.5">
          <div className="flex items-start gap-2">
            <Loader2 size={14} className="mt-0.5 shrink-0 animate-spin text-brand" />
            <div className="min-w-0 flex-1">
              <p className="font-medium text-text-primary">可审计处理过程</p>
              <p className="mt-0.5 text-[10px] leading-4 opacity-70">显示检索与核验阶段，不展示模型隐藏的逐字思维链。</p>
            </div>
            <span className="shrink-0 font-mono text-[11px] font-semibold tabular-nums text-brand" aria-hidden="true">{progress}%</span>
          </div>
          <ol className="mt-2.5 flex flex-wrap gap-1.5">
            {steps.map((step, index) => {
              const complete = index < currentStep;
              const current = index === currentStep;
              return (
                <li
                  key={step}
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] transition-colors ${
                    complete
                      ? "border-[#68C8BC]/25 bg-[#EFF9F6] text-[#287E75]"
                      : current
                        ? "border-brand/25 bg-brand/5 font-medium text-brand"
                        : "border-black/5 bg-white/70 text-text-secondary/55"
                  }`}
                >
                  {complete ? <CheckCircle2 size={11} /> : current ? <Loader2 size={11} className="animate-spin" /> : <Circle size={10} />}
                  {step}
                </li>
              );
            })}
          </ol>
          <p className="mt-2 font-medium text-brand">当前：{steps[currentStep]}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      role="status"
      className="mt-2 flex items-center justify-between gap-3 rounded-xl bg-bg-page px-3 py-2 text-xs text-text-secondary"
    >
      <span className="flex min-w-0 items-center gap-2">
        <Icon size={14} className={isActive ? "animate-spin text-brand" : "shrink-0"} />
        <span>{state.error ?? runPhaseLabel[state.phase]}</span>
        {state.route ? <span className="hidden font-mono text-[10px] opacity-60 sm:inline">{state.route}</span> : null}
      </span>
      {!isActive && onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 font-medium text-brand hover:bg-brand/5"
        >
          <RotateCcw size={13} /> 重新生成
        </button>
      ) : null}
    </div>
  );
}
