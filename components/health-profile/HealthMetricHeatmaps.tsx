"use client";

import { Flame, Footprints, Info, Moon } from "lucide-react";
import type { FastRecord } from "@/lib/api/fasting";
import type { ObservationRecord } from "@/lib/api/health-profile";

type HeatmapKind = "steps" | "sleep" | "fasting";
type DayCell = { key: string; date: Date; value: number | null };

const DAY_MS = 86_400_000;

const heatmapMeta: Record<HeatmapKind, {
  title: string;
  unit: string;
  color: string;
  icon: typeof Footprints;
  thresholds: [number, number, number, number];
  empty: string;
  note: string;
}> = {
  steps: {
    title: "步数",
    unit: "步",
    color: "#3F7FD7",
    icon: Footprints,
    thresholds: [2000, 5000, 8000, 12000],
    empty: "没有步数记录",
    note: "按当天已记录步数汇总",
  },
  sleep: {
    title: "睡眠",
    unit: "分钟",
    color: "#6687AF",
    icon: Moon,
    thresholds: [240, 360, 480, 600],
    empty: "没有睡眠记录",
    note: "按当天已记录睡眠时长汇总",
  },
  fasting: {
    title: "燃脂观察",
    unit: "小时",
    color: "#D27C3E",
    icon: Flame,
    thresholds: [8, 12, 14, 16],
    empty: "没有进食间隔记录",
    note: "按轻断食记录的进食间隔展示",
  },
};

function dateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatDate(date: Date) {
  return date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

function localDateKey(iso: string) {
  return dateKey(new Date(iso));
}

function buildDays(): DayCell[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today.getTime() - 83 * DAY_MS);
  return Array.from({ length: 84 }, (_, index) => {
    const date = new Date(start.getTime() + index * DAY_MS);
    return { key: dateKey(date), date, value: null };
  });
}

function level(value: number | null, thresholds: [number, number, number, number]) {
  if (value == null || value <= 0) return 0;
  if (value < thresholds[0]) return 1;
  if (value < thresholds[1]) return 2;
  if (value < thresholds[2]) return 3;
  if (value < thresholds[3]) return 4;
  return 5;
}

function displayValue(kind: HeatmapKind, value: number | null) {
  if (value == null) return "未记录";
  if (kind === "fasting") return `${value.toFixed(1)} 小时`;
  return `${Math.round(value).toLocaleString("zh-CN")} ${heatmapMeta[kind].unit}`;
}

function buildValues(observations: ObservationRecord[], fasts: FastRecord[]) {
  const values: Record<HeatmapKind, Map<string, number>> = {
    steps: new Map(),
    sleep: new Map(),
    fasting: new Map(),
  };

  observations.forEach((record) => {
    if (record.value == null || (record.kind !== "steps" && record.kind !== "sleep_minutes")) return;
    const kind = record.kind === "steps" ? "steps" : "sleep";
    const key = localDateKey(record.observed_at);
    values[kind].set(key, (values[kind].get(key) ?? 0) + record.value);
  });

  fasts.forEach((record) => {
    if (!record.end_at && record.status !== "active") return;
    const end = record.end_at ? new Date(record.end_at).getTime() : Date.now();
    const hours = Math.max(0, (end - new Date(record.start_at).getTime()) / 3_600_000);
    const key = localDateKey(record.start_at);
    values.fasting.set(key, (values.fasting.get(key) ?? 0) + hours);
  });

  return values;
}

function Heatmap({ kind, values }: { kind: HeatmapKind; values: Map<string, number> }) {
  const meta = heatmapMeta[kind];
  const Icon = meta.icon;
  const days = buildDays().map((day) => ({ ...day, value: values.get(day.key) ?? null }));
  const recordedDays = days.filter((day) => day.value != null).length;
  const latest = [...days].reverse().find((day) => day.value != null);
  const monthLabels = days.reduce<Array<{ key: string; label: string; index: number }>>((labels, day, index) => {
    const key = `${day.date.getFullYear()}-${day.date.getMonth() + 1}`;
    if (!labels.some((label) => label.key === key) && index > 0) {
      labels.push({ key, label: `${day.date.getMonth() + 1}月`, index });
    }
    return labels;
  }, []);

  return (
    <article className="min-w-0 rounded-[18px] border border-border-divider bg-[#FBFCFC] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-xl" style={{ backgroundColor: `${meta.color}16`, color: meta.color }}>
            <Icon size={17} />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-text-primary">{meta.title}</h3>
            <p className="mt-0.5 text-[10px] text-text-secondary">{meta.note}</p>
          </div>
        </div>
        <span className="text-[10px] text-text-secondary">近 12 周</span>
      </div>

      <div className="mt-4 overflow-x-auto pb-1">
        <div className="relative min-w-[330px] pl-5">
          <div className="relative ml-0 h-4 text-[9px] text-text-secondary">
            {monthLabels.map((month) => (
              <span key={month.key} className="absolute" style={{ left: `${(month.index / 84) * 100}%` }}>{month.label}</span>
            ))}
          </div>
          <div className="grid grid-cols-[14px_repeat(12,minmax(16px,1fr))] gap-[3px]">
            <div className="grid grid-rows-7 gap-[3px] text-[9px] leading-[16px] text-text-secondary">
              <span>一</span><span></span><span>三</span><span></span><span>五</span><span></span><span>日</span>
            </div>
            {Array.from({ length: 12 }, (_, week) => (
              <div key={week} className="grid grid-rows-7 gap-[3px]">
                {days.slice(week * 7, week * 7 + 7).map((day) => {
                  const cellLevel = level(day.value, meta.thresholds);
                  return (
                    <div
                      key={day.key}
                      role="img"
                      aria-label={`${formatDate(day.date)}：${displayValue(kind, day.value)}`}
                      title={`${formatDate(day.date)} · ${displayValue(kind, day.value)}`}
                      className="h-4 min-w-0 rounded-[3px] border border-black/[0.035]"
                      style={{ backgroundColor: day.value == null ? "#E9EEEC" : `${meta.color}${["18", "42", "68", "92", "B8", "E8"][cellLevel]}` }}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 text-[10px] text-text-secondary">
        <span>{recordedDays ? `有记录 ${recordedDays} 天` : meta.empty}</span>
        <span>{latest ? `最近 ${displayValue(kind, latest.value)}` : "—"}</span>
      </div>
      <div className="mt-2 flex items-center justify-end gap-1.5 text-[9px] text-text-secondary">
        <span>少</span>
        {["18", "42", "68", "92", "B8", "E8"].map((alpha) => <span key={alpha} className="h-2.5 w-2.5 rounded-[2px]" style={{ backgroundColor: `${meta.color}${alpha}` }} aria-hidden="true" />)}
        <span>多</span>
      </div>
    </article>
  );
}

export function HealthMetricHeatmaps({ observations, fasts }: { observations: ObservationRecord[]; fasts: FastRecord[] }) {
  const values = buildValues(observations, fasts);
  return (
    <section className="mt-3 rounded-[22px] border border-border-divider bg-white p-5 shadow-[0_12px_35px_rgba(35,50,48,0.035)] sm:p-6" aria-label="近十二周健康热力图">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-text-primary">近 12 周节律热力图</h2>
          <p className="mt-1 text-xs leading-5 text-text-secondary">颜色越深，代表当天记录值越高；灰色是没有记录，不是零值。</p>
        </div>
        <span className="inline-flex items-center gap-1 text-[10px] text-text-secondary"><Info size={12} />只展示已保存数据</span>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Heatmap kind="sleep" values={values.sleep} />
        <Heatmap kind="fasting" values={values.fasting} />
        <Heatmap kind="steps" values={values.steps} />
      </div>
      <p className="mt-3 text-[10px] leading-5 text-text-secondary">“燃脂观察”只按已记录的进食间隔着色，不能据此确认脂肪消耗或减重效果。</p>
    </section>
  );
}
