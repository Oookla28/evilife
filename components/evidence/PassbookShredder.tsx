"use client";

import { useRef, useState, useEffect } from "react";
import { Trash2, RefreshCw, CheckCircle2 } from "lucide-react";
import {
  PassbookShredScene,
  SHRED_TOTAL_MS,
} from "@/components/evidence/PassbookShredScene";

interface PassbookShredderProps {
  title?: string;
  subtitle?: string;
  details?: string;
  onShredComplete?: () => void;
}

export function PassbookShredder({
  title = "健康记录卡片 (例如：今日餐食记录)",
  subtitle = "热量: 520 kcal · 包含高钠食品",
  details = "记录 ID: REC-20260811-09",
  onShredComplete,
}: PassbookShredderProps) {
  const [state, setState] = useState<"idle" | "shredding" | "done">("idle");
  const timers = useRef<number[]>([]);

  useEffect(
    () => () => timers.current.forEach((t) => window.clearTimeout(t)),
    [],
  );

  const start = () => {
    if (state !== "idle") return;
    setState("shredding");
    const tid = window.setTimeout(() => {
      setState("done");
      onShredComplete?.();
    }, SHRED_TOTAL_MS);
    timers.current.push(tid);
  };

  return (
    <div className="w-full max-w-md mx-auto my-6 flex flex-col items-center select-none">
      <div className="flex items-center justify-between w-full mb-3 px-1">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider flex items-center gap-1.5">
          <Trash2 size={14} className="text-risk-refused" />
          iOS 6 Passbook 碎纸机
        </span>
        {state === "done" && (
          <button
            onClick={() => setState("idle")}
            className="text-xs text-brand hover:underline flex items-center gap-1"
          >
            <RefreshCw size={12} />
            重置
          </button>
        )}
      </div>

      <div
        className="relative w-full rounded-3xl p-5 shadow-2xl border border-slate-800 overflow-hidden flex flex-col items-center"
        style={{ background: "#111", minHeight: 360 }}
      >
        {state === "idle" && (
          <>
            <div
              className="w-full text-white rounded-2xl p-5 mb-4"
              style={{
                background: "linear-gradient(135deg,#d97706,#ea580c)",
                boxShadow: "0 8px 24px rgba(0,0,0,.35)",
              }}
            >
              <div className="text-xs font-mono opacity-80 mb-2">PASSBOOK RECORD</div>
              <div className="font-bold text-lg mb-1">{title}</div>
              <div className="text-xs opacity-90 mb-3">{subtitle}</div>
              <div className="text-[10px] opacity-70 font-mono border-t border-white/20 pt-2">
                {details}
              </div>
            </div>
            <button
              onClick={start}
              className="px-4 py-2 bg-risk-refused text-white rounded-xl text-sm font-medium flex items-center gap-2"
            >
              <Trash2 size={14} />
              确认撕碎销毁
            </button>
          </>
        )}

        {state === "shredding" && (
          <PassbookShredScene
            card={{
              title,
              tag: "PASSBOOK",
              body: subtitle,
              color: "#c2410c",
            }}
          />
        )}

        {state === "done" && (
          <div className="flex flex-col items-center gap-3 text-emerald-400 py-10">
            <div className="w-14 h-14 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
              <CheckCircle2 size={32} />
            </div>
            <span className="font-semibold text-sm">卡片已被碎纸机销毁</span>
          </div>
        )}
      </div>
    </div>
  );
}
