"use client";

import { useEffect, useMemo, useState } from "react";
import { Clock3, Play, Square, TimerReset } from "lucide-react";
import {
  endFast,
  getActiveFast,
  getFasts,
  startFast,
  type FastRecord,
} from "@/lib/api/fasting";

const PRESETS = [14, 16, 18] as const;
const RADIUS = 62;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function formatElapsed(milliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds]
    .map((value) => value.toString().padStart(2, "0"))
    .join(":");
}

function durationHours(record: FastRecord) {
  if (!record.end_at) return 0;
  return (
    (new Date(record.end_at).getTime() - new Date(record.start_at).getTime()) /
    3_600_000
  );
}

export function FastingTimer() {
  const [active, setActive] = useState<FastRecord | null>(null);
  const [history, setHistory] = useState<FastRecord[]>([]);
  const [goalHours, setGoalHours] = useState<number>(16);
  const [now, setNow] = useState(0);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([getActiveFast(), getFasts()])
      .then(([current, records]) => {
        if (cancelled) return;
        setActive(current);
        setHistory(records.filter((record) => record.status === "completed"));
        setError("");
      })
      .catch(() => {
        if (!cancelled) setError("计时服务暂时不可用，请确认后端已启动。");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!active) return;
    const tick = () => setNow(Date.now());
    const firstTick = window.setTimeout(tick, 0);
    const timer = window.setInterval(tick, 1000);
    return () => {
      window.clearTimeout(firstTick);
      window.clearInterval(timer);
    };
  }, [active]);

  const elapsed = active
    ? Math.max(0, now - new Date(active.start_at).getTime())
    : 0;
  const goalMilliseconds = (active?.goal_hours ?? goalHours) * 3_600_000;
  const progress = Math.min(1, elapsed / goalMilliseconds);
  const dashOffset = CIRCUMFERENCE * (1 - progress);
  const targetTime = useMemo(() => {
    if (!active) return null;
    return new Date(
      new Date(active.start_at).getTime() + active.goal_hours * 3_600_000
    );
  }, [active]);

  const handleStart = async () => {
    setWorking(true);
    setError("");
    try {
      const record = await startFast(goalHours);
      setActive(record);
      setNow(Date.now());
    } catch {
      setError("没有启动计时；可能已有一个计时正在进行。");
    } finally {
      setWorking(false);
    }
  };

  const handleEnd = async () => {
    if (!active) return;
    setWorking(true);
    setError("");
    try {
      const completed = await endFast(active.id);
      setHistory((records) => [completed, ...records]);
      setActive(null);
      setConfirmEnd(false);
    } catch {
      setError("没有结束计时，请刷新后重试。");
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="overflow-hidden rounded-[28px] border border-[#DEDDE7] bg-white shadow-[0_18px_55px_rgba(43,39,70,0.07)]">
      <div className="flex items-center justify-between border-b border-[#ECEBF1] px-5 py-4 sm:px-6">
        <div>
          <p className="text-[11px] font-semibold tracking-[0.16em] text-[#77738B] uppercase">
            客观时间记录
          </p>
          <h2 className="mt-1 text-lg font-semibold text-text-primary">进食间隔计时</h2>
        </div>
        <TimerReset className="text-[#6F6A9A]" size={22} aria-hidden="true" />
      </div>

      <div className="grid gap-6 p-5 sm:grid-cols-[180px_1fr] sm:p-6">
        <div className="relative mx-auto grid h-[164px] w-[164px] place-items-center">
          <svg className="absolute inset-0 -rotate-90" viewBox="0 0 144 144" aria-hidden="true">
            <circle cx="72" cy="72" r={RADIUS} fill="none" stroke="#EEEFF3" strokeWidth="8" />
            <circle
              cx="72"
              cy="72"
              r={RADIUS}
              fill="none"
              stroke="#6F6A9A"
              strokeLinecap="round"
              strokeWidth="8"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={dashOffset}
              className="transition-[stroke-dashoffset] duration-700"
            />
          </svg>
          <div className="relative text-center" aria-live="polite">
            <p className="font-mono text-[22px] font-semibold tracking-tight text-text-primary">
              {loading ? "--:--:--" : formatElapsed(elapsed)}
            </p>
            <p className="mt-1 text-xs text-text-secondary">
              {active ? `${Math.round(progress * 100)}% 时间进度` : "尚未开始"}
            </p>
          </div>
        </div>

        <div className="flex min-w-0 flex-col justify-center">
          {active ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl bg-[#F6F5FA] p-3">
                  <p className="text-xs text-text-secondary">记录目标</p>
                  <p className="mt-1 font-semibold text-text-primary">{active.goal_hours} 小时</p>
                </div>
                <div className="rounded-2xl bg-[#F6F5FA] p-3">
                  <p className="text-xs text-text-secondary">目标时间</p>
                  <p className="mt-1 font-semibold text-text-primary">
                    {targetTime?.toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              </div>
              {confirmEnd ? (
                <div className="mt-4 rounded-2xl border border-[#DEDDE7] bg-[#FBFAFD] p-4">
                  <p className="text-sm font-medium text-text-primary">结束并保存这段客观记录？</p>
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => setConfirmEnd(false)}
                      className="rounded-xl border border-border-divider px-4 py-2 text-sm text-text-primary outline-none focus-visible:ring-2 focus-visible:ring-brand"
                    >
                      继续计时
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleEnd()}
                      disabled={working}
                      className="rounded-xl bg-[#625D8D] px-4 py-2 text-sm font-medium text-white outline-none disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-[#625D8D] focus-visible:ring-offset-2"
                    >
                      {working ? "保存中…" : "结束并保存"}
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmEnd(true)}
                  className="mt-4 inline-flex w-fit items-center gap-2 rounded-xl bg-[#625D8D] px-4 py-2.5 text-sm font-medium text-white outline-none focus-visible:ring-2 focus-visible:ring-[#625D8D] focus-visible:ring-offset-2"
                >
                  <Square size={15} fill="currentColor" />结束计时
                </button>
              )}
            </>
          ) : (
            <>
              <p className="text-sm leading-6 text-text-secondary">
                选择一个时间目标。计时器只保存开始、结束和时长，不据此生成减重或代谢建议。
              </p>
              <div className="mt-4 flex flex-wrap gap-2" aria-label="时间目标">
                {PRESETS.map((hours) => (
                  <button
                    type="button"
                    key={hours}
                    onClick={() => setGoalHours(hours)}
                    aria-pressed={goalHours === hours}
                    className={`rounded-full border px-3.5 py-1.5 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-brand ${
                      goalHours === hours
                        ? "border-[#625D8D] bg-[#F0EFF7] text-[#4F4A78]"
                        : "border-border-divider text-text-secondary hover:border-[#A9A5C2]"
                    }`}
                  >
                    {hours === 16 ? "16:8" : `${hours} 小时`}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => void handleStart()}
                disabled={working || loading}
                className="mt-4 inline-flex w-fit items-center gap-2 rounded-xl bg-[#625D8D] px-4 py-2.5 text-sm font-medium text-white outline-none disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-[#625D8D] focus-visible:ring-offset-2"
              >
                <Play size={16} fill="currentColor" />
                {working ? "启动中…" : "开始记录"}
              </button>
            </>
          )}

          {error ? <p className="mt-3 text-sm text-risk-refused" role="alert">{error}</p> : null}
        </div>
      </div>

      {history.length > 0 ? (
        <div className="border-t border-[#ECEBF1] px-5 py-4 sm:px-6">
          <div className="flex items-center gap-2 text-xs font-medium text-text-secondary">
            <Clock3 size={14} />最近完成
          </div>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-text-primary">
            {history.slice(0, 3).map((record) => (
              <span key={record.id}>{durationHours(record).toFixed(1)} 小时</span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

export { formatElapsed };
