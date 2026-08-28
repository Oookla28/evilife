"use client";

import { useEffect, useMemo, useState } from "react";
import { CircleStop, Play, ShieldCheck } from "lucide-react";
import { endFast, startFast, type FastRecord } from "@/lib/api/fasting";
import { formatElapsed } from "@/components/lifestyle/FastingTimer";

const plans = [12, 14, 16] as const;

export function ExperimentFastingPanel({ initialActive, onChanged }: { initialActive: FastRecord | null; onChanged: () => void }) {
  const [active, setActive] = useState(initialActive);
  const [goal, setGoal] = useState(12);
  const [now, setNow] = useState(0);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  const elapsed = active ? Math.max(0, now - new Date(active.start_at).getTime()) : 0;
  const progress = active ? Math.min(1, elapsed / (active.goal_hours * 3_600_000)) : 0;
  const target = useMemo(() => active ? new Date(new Date(active.start_at).getTime() + active.goal_hours * 3_600_000) : null, [active]);

  const toggle = async () => {
    setWorking(true);
    setError("");
    try {
      if (active) {
        await endFast(active.id);
        setActive(null);
      } else {
        const record = await startFast(goal);
        setActive(record);
        setNow(Date.now());
      }
      onChanged();
    } catch {
      setError("计时记录没有更新，请稍后重试。");
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="rounded-[22px] border border-[#DDE5E3] bg-white px-5 py-5 shadow-[0_14px_40px_rgba(40,67,63,0.055)] sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">轻断食实验</h2>
          <p className="mt-1 text-xs text-text-secondary">只记录进食间隔时间，不推断减脂或代谢效果。</p>
        </div>
        {!active ? <div className="flex rounded-xl bg-[#F3F7F6] p-1" aria-label="断食记录方案">
          {plans.map((hours) => <button key={hours} type="button" onClick={() => setGoal(hours)} aria-pressed={goal === hours} className={`rounded-lg px-3 py-1.5 text-xs font-medium ${goal === hours ? "bg-white text-brand shadow-sm" : "text-text-secondary"}`}>{hours}:{24 - hours}</button>)}
        </div> : <span className="rounded-full bg-brand/[0.08] px-3 py-1.5 text-xs font-medium text-brand">{active.goal_hours}:{24 - active.goal_hours}</span>}
      </div>

      <div className="mt-5 grid items-center gap-5 md:grid-cols-[140px_1fr_210px]">
        <div className="relative mx-auto h-[126px] w-[126px]">
          <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90" aria-hidden="true">
            <circle cx="60" cy="60" r="51" fill="none" stroke="#E8EFED" strokeWidth="8" />
            <circle cx="60" cy="60" r="51" fill="none" stroke="#4D8A82" strokeWidth="8" strokeLinecap="round" pathLength="100" strokeDasharray="100" strokeDashoffset={100 - progress * 100} className="transition-[stroke-dashoffset] duration-700" />
          </svg>
          <div className="absolute inset-0 grid place-content-center text-center"><span className="text-xl font-semibold text-brand">{active ? `${Math.round(progress * 100)}%` : `${goal}:${24 - goal}`}</span><span className="mt-1 text-[11px] text-text-secondary">{active ? "时间进度" : "当前方案"}</span></div>
        </div>

        <div className="min-w-0 border-border-divider md:border-r md:pr-6">
          <p className="text-xs text-text-secondary">{active ? "已经记录" : "尚未开始"}</p>
          <p className="mt-1 font-mono text-3xl font-semibold tracking-tight text-text-primary">{formatElapsed(elapsed)}</p>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div><p className="text-xs text-text-secondary">开始时间</p><p className="mt-1 font-medium">{active ? new Date(active.start_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "--:--"}</p></div>
            <div><p className="text-xs text-text-secondary">预计结束</p><p className="mt-1 font-medium">{target ? target.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "--:--"}</p></div>
          </div>
        </div>

        <div className="flex flex-col items-start md:items-center">
          <button type="button" disabled={working} onClick={() => void toggle()} className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium ${active ? "border border-brand text-brand" : "bg-brand text-white"}`}>
            {active ? <CircleStop size={16} /> : <Play size={16} fill="currentColor" />}{working ? "处理中…" : active ? "结束本次记录" : "开始记录"}
          </button>
          <p className="mt-3 flex max-w-[210px] items-start gap-1.5 text-[11px] leading-5 text-text-secondary"><ShieldCheck size={14} className="mt-0.5 shrink-0 text-brand" />如有不适请停止，并寻求专业建议。</p>
        </div>
      </div>
      {error ? <p role="alert" className="mt-3 text-sm text-risk-refused">{error}</p> : null}
    </section>
  );
}
