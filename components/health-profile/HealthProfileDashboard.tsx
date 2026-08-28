"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bot,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Droplets,
  Footprints,
  Moon,
  Pencil,
  Plus,
  Scale,
  Smartphone,
  Utensils,
  UserRound,
} from "lucide-react";
import { getTodayRecords, type TodayRecords } from "@/lib/api/today";
import {
  getObservations,
  type CompletedAppleHealthImport,
  type ObservationKind,
  type ObservationRecord,
  type ObservationSource,
} from "@/lib/api/health-profile";
import { getFasts, type FastRecord } from "@/lib/api/fasting";
import { AddRecordSheet } from "./AddRecordSheet";
import { ExperimentFastingPanel } from "./ExperimentFastingPanel";
import { HealthInsightFlow } from "./HealthInsightFlow";
import { HealthMetricHeatmaps } from "./HealthMetricHeatmaps";
import { ReportAnalysisPanel } from "./ReportAnalysisPanel";

const sourceMeta: Record<ObservationSource, { label: string; detail: string; color: string }> = {
  self_report: { label: "自报", detail: "本人手动记录", color: "#4D8A82" },
  device: { label: "设备", detail: "尚未接入设备", color: "#3F7FD7" },
  ai_estimate: { label: "AI估算", detail: "基于数据估算", color: "#B8751A" },
};

const observationMeta: Record<ObservationKind, { label: string; unit: string }> = {
  water_ml: { label: "饮水", unit: "ml" },
  steps: { label: "步行", unit: "步" },
  sleep_minutes: { label: "睡眠", unit: "分钟" },
  weight_kg: { label: "体重", unit: "kg" },
  waist_cm: { label: "腰围", unit: "cm" },
  resting_heart_rate: { label: "静息心率", unit: "次/分" },
  mood_score: { label: "心情", unit: "/ 5" },
  note: { label: "备注", unit: "" },
};

function latest(records: ObservationRecord[], kind: ObservationKind) {
  return records.find((record) => record.kind === kind);
}

function formatSleep(minutes?: number | null) {
  if (minutes == null) return "未记录";
  return `${Math.floor(minutes / 60)}小时${Math.round(minutes % 60)}分`;
}

function WeightChart({ records }: { records: ObservationRecord[] }) {
  const points = records
    .filter((record) => record.kind === "weight_kg" && record.value != null)
    .slice(0, 14)
    .reverse();
  if (points.length < 2) {
    return <div className="grid h-40 place-items-center rounded-xl border border-dashed border-border-divider text-sm text-text-secondary">添加至少 2 条体重记录后显示趋势</div>;
  }
  const values = points.map((point) => point.value as number);
  const min = Math.min(...values) - 0.5;
  const max = Math.max(...values) + 0.5;
  const range = Math.max(1, max - min);
  const coordinates = values.map((value, index) => ({
    x: 20 + index * (480 / Math.max(1, values.length - 1)),
    y: 135 - ((value - min) / range) * 105,
  }));
  const path = coordinates.map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`).join(" ");
  return (
    <div className="h-40 w-full" aria-label="体重趋势图">
      <svg viewBox="0 0 520 160" className="h-full w-full overflow-visible" role="img">
        {[30, 65, 100, 135].map((y) => <line key={y} x1="20" x2="500" y1={y} y2={y} stroke="#E9ECEB" strokeDasharray="4 5" />)}
        <path d={`${path} L${coordinates.at(-1)?.x},145 L20,145 Z`} fill="rgba(77,138,130,0.08)" />
        <path d={path} fill="none" stroke="#4D8A82" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {coordinates.map((point, index) => <circle key={points[index].id} cx={point.x} cy={point.y} r="4" fill="#4D8A82"><title>{values[index]} kg</title></circle>)}
      </svg>
    </div>
  );
}

export function HealthProfileDashboard() {
  const todayKey = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [dateKey, setDateKey] = useState(todayKey);
  const [today, setToday] = useState<TodayRecords | null>(null);
  const [allObservations, setAllObservations] = useState<ObservationRecord[]>([]);
  const [allFasts, setAllFasts] = useState<FastRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetKind, setSheetKind] = useState<ObservationKind>("water_ml");
  const [metricTab, setMetricTab] = useState<ObservationKind>("weight_kg");
  const [lastAppleImport, setLastAppleImport] = useState<CompletedAppleHealthImport | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [summary, observations, fasts] = await Promise.all([getTodayRecords(dateKey), getObservations(undefined, 5000), getFasts(100)]);
      setToday(summary);
      setAllObservations(observations);
      setAllFasts(fasts);
      setError("");
    } catch {
      setError("健康档案服务暂时不可用，请确认后端已启动。");
    } finally {
      setLoading(false);
    }
  }, [dateKey]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getTodayRecords(dateKey), getObservations(undefined, 5000), getFasts(100)])
      .then(([summary, observations, fasts]) => {
        if (cancelled) return;
        setToday(summary);
        setAllObservations(observations);
        setAllFasts(fasts);
        setError("");
      })
      .catch(() => {
        if (!cancelled) setError("健康档案服务暂时不可用，请确认后端已启动。");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [dateKey]);

  const openSheet = (kind: ObservationKind) => {
    setSheetKind(kind);
    setSheetOpen(true);
  };

  const moveDate = (days: number) => {
    const selected = new Date(`${dateKey}T12:00:00`);
    selected.setDate(selected.getDate() + days);
    const next = selected.toISOString().slice(0, 10);
    if (next <= todayKey) setDateKey(next);
  };

  const todayObservations = useMemo(() => today?.observations ?? [], [today?.observations]);
  const water = todayObservations.filter((record) => record.kind === "water_ml").reduce((total, record) => total + (record.value ?? 0), 0);
  const steps = latest(todayObservations, "steps")?.value;
  const sleep = latest(todayObservations, "sleep_minutes")?.value;
  const weight = latest(todayObservations, "weight_kg")?.value;
  const completed = [water > 0, (today?.meals.length ?? 0) > 0, steps != null, sleep != null, weight != null].filter(Boolean).length;
  const activeFast = today?.fasts.find((record) => record.status === "active") ?? null;
  const experimentDay = useMemo(() => {
    if (allObservations.length === 0) return 1;
    const first = Math.min(...allObservations.map((record) => new Date(record.observed_at).setHours(0, 0, 0, 0)));
    const selected = new Date(`${dateKey}T12:00:00`).setHours(0, 0, 0, 0);
    return Math.max(1, Math.floor((selected - first) / 86_400_000) + 1);
  }, [allObservations, dateKey]);

  const metrics = [
    { label: "饮水", value: water > 0 ? `${water.toLocaleString()} ml` : "未记录", kind: "water_ml" as const, icon: Droplets, color: "#4D8A82" },
    { label: "餐食", value: `${today?.meals.length ?? 0} 次`, kind: null, icon: Utensils, color: "#4D8A82" },
    { label: "步数", value: steps != null ? `${steps.toLocaleString()} 步` : "未记录", kind: "steps" as const, icon: Footprints, color: "#3F7FD7" },
    { label: "睡眠", value: formatSleep(sleep), kind: "sleep_minutes" as const, icon: Moon, color: "#3F7FD7" },
    { label: "体重", value: weight != null ? `${weight.toFixed(1)} kg` : "未记录", kind: "weight_kg" as const, icon: Scale, color: "#4D8A82" },
  ];

  const events = useMemo(() => {
    const observationEvents = todayObservations.map((record) => ({
      id: record.id,
      at: record.observed_at,
      label: observationMeta[record.kind].label,
      value: record.kind === "note" ? record.note ?? "" : `${record.value?.toLocaleString()} ${observationMeta[record.kind].unit}`,
      source: record.source,
    }));
    const mealEvents = (today?.meals ?? []).map((meal) => ({ id: meal.id, at: meal.created_at, label: "餐食", value: "已确认", source: "ai_estimate" as const }));
    return [...observationEvents, ...mealEvents].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  }, [today?.meals, todayObservations]);

  return (
    <div className="relative mx-auto w-full max-w-[1320px] px-4 pb-24 pt-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div><h1 className="text-[28px] font-semibold tracking-tight text-text-primary">实验者健康档案</h1><p className="mt-1.5 text-sm text-text-secondary">记录事实，观察变化，不替代医学判断</p></div>
        <div className="flex flex-wrap items-center gap-2.5">
          {(Object.entries(sourceMeta) as [ObservationSource, (typeof sourceMeta)[ObservationSource]][]).map(([source, meta]) => {
            const Icon = source === "self_report" ? UserRound : source === "device" ? Smartphone : Bot;
            return <div key={source} title={meta.detail} className="flex items-center gap-2 rounded-xl border border-border-divider bg-white px-3 py-2"><Icon size={15} style={{ color: meta.color }} /><div><p className="text-xs font-medium text-text-primary">{meta.label}</p><p className="text-[10px] text-text-secondary">{meta.detail}</p></div></div>;
          })}
          <div className="ml-0 flex items-center gap-2 rounded-full border border-border-divider bg-white px-2 py-1.5 text-sm text-text-primary lg:ml-2">
            <button type="button" onClick={() => moveDate(-1)} aria-label="查看前一天" className="rounded-full p-1 text-text-secondary hover:bg-black/5"><ChevronLeft size={15} /></button>
            <CalendarDays size={15} className="text-brand" />
            <span>{new Date(`${dateKey}T12:00:00`).toLocaleDateString("zh-CN", { month: "long", day: "numeric" })} · 第 {experimentDay} 天</span>
            <button type="button" onClick={() => moveDate(1)} disabled={dateKey >= todayKey} aria-label="查看后一天" className="rounded-full p-1 text-text-secondary hover:bg-black/5 disabled:opacity-25"><ChevronRight size={15} /></button>
          </div>
        </div>
      </header>

      {error ? <p role="alert" className="mt-4 rounded-xl bg-risk-refused/5 px-4 py-3 text-sm text-risk-refused">{error}</p> : null}

      {!loading ? <HealthInsightFlow observations={allObservations} appleImport={lastAppleImport} onAppleImportComplete={(result) => { setLastAppleImport(result); void refresh(); }} onObservationDeleted={(id) => { setAllObservations((items) => items.filter((item) => item.id !== id)); setToday((summary) => summary ? { ...summary, observations: summary.observations.filter((item) => item.id !== id) } : summary); }} /> : null}

      <ReportAnalysisPanel />

      <section className="mt-6 flex flex-col items-center gap-5 rounded-[22px] border border-border-divider bg-white px-5 py-5 shadow-[0_12px_35px_rgba(35,50,48,0.035)] sm:flex-row sm:px-7">
        <div className="relative grid h-[116px] w-[116px] shrink-0 place-content-center text-center">
          <svg viewBox="0 0 112 112" className="absolute inset-0 -rotate-90" aria-hidden="true"><circle cx="56" cy="56" r="47" fill="none" stroke="#E7ECEB" strokeWidth="7" /><circle cx="56" cy="56" r="47" fill="none" stroke="#4D8A82" strokeWidth="7" strokeLinecap="round" pathLength="100" strokeDasharray="100" strokeDashoffset={100 - completed * 20} className="transition-[stroke-dashoffset] duration-700" /></svg>
          <p className="text-xs text-text-secondary">今日记录</p><p className="mt-1 text-2xl font-semibold text-text-primary">{loading ? "–/–" : `${completed}/5`}</p>
        </div>
        <div><p className="text-base font-medium text-text-primary">{completed === 5 ? "今天的五类观察已完整" : `还可补充 ${5 - completed} 类观察`}</p><p className="mt-1.5 text-sm leading-6 text-text-secondary">饮水、餐食、步数、睡眠和体重用于整理实验过程；缺失数据会保持为空，不进行推断补齐。</p></div>
      </section>

      <section className="mt-3 grid overflow-hidden rounded-[20px] border border-border-divider bg-white sm:grid-cols-2 lg:grid-cols-5" aria-label="今日关键记录">
        {metrics.map((metric, index) => { const Icon = metric.icon; return <div key={metric.label} className={`group relative min-w-0 px-5 py-4 ${index > 0 ? "border-t border-border-divider sm:border-t-0 sm:border-l" : ""}`}><div className="flex items-center gap-2 text-xs text-text-secondary"><Icon size={16} style={{ color: metric.color }} />{metric.label}</div><p className="mt-2 truncate text-lg font-medium text-text-primary" style={{ color: metric.value === "未记录" ? undefined : metric.color }}>{metric.value}</p>{metric.kind ? <button type="button" onClick={() => openSheet(metric.kind)} aria-label={`记录${metric.label}`} className="absolute right-3 top-3 rounded-lg p-1.5 text-text-secondary opacity-70 hover:bg-black/5 group-hover:opacity-100"><Pencil size={14} /></button> : null}</div>; })}
      </section>

      <div className="mt-3"><ExperimentFastingPanel key={activeFast?.id ?? "idle"} initialActive={activeFast} onChanged={() => void refresh()} /></div>

      <HealthMetricHeatmaps observations={allObservations} fasts={allFasts} />

      <div className="mt-3 grid gap-3 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-[22px] border border-border-divider bg-white p-5 shadow-[0_12px_35px_rgba(35,50,48,0.035)] sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-text-primary">身体指标趋势</h2><p className="mt-1 text-xs text-text-secondary">仅呈现已记录数值，不做健康等级判断</p></div><span className="rounded-lg border border-border-divider px-2.5 py-1.5 text-xs text-text-secondary">本人手动记录</span></div>
          <div className="mt-4 flex gap-5 border-b border-border-divider text-sm">{(["weight_kg", "waist_cm", "resting_heart_rate"] as ObservationKind[]).map((kind) => <button type="button" key={kind} onClick={() => setMetricTab(kind)} className={`border-b-2 px-1 pb-2.5 ${metricTab === kind ? "border-brand font-medium text-brand" : "border-transparent text-text-secondary"}`}>{observationMeta[kind].label}</button>)}</div>
          <div className="mt-4">{metricTab === "weight_kg" ? <WeightChart records={allObservations} /> : <div className="grid h-40 place-items-center rounded-xl border border-dashed border-border-divider text-sm text-text-secondary">{observationMeta[metricTab].label}趋势将在记录至少 2 次后显示</div>}</div>
        </section>

        <section className="rounded-[22px] border border-border-divider bg-white p-5 shadow-[0_12px_35px_rgba(35,50,48,0.035)] sm:p-6">
          <div className="flex items-center justify-between"><div><h2 className="text-base font-semibold text-text-primary">今日事件</h2><p className="mt-1 text-xs text-text-secondary">按实际记录时间排列</p></div><Activity size={18} className="text-brand" /></div>
          <div className="mt-5 space-y-1">
            {events.length ? events.map((event) => { const meta = sourceMeta[event.source]; return <div key={event.id} className="grid grid-cols-[48px_10px_1fr] items-start gap-2 py-2.5"><time className="pt-0.5 text-xs text-text-secondary">{new Date(event.at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</time><span className="mt-1.5 h-2 w-2 rounded-full" style={{ background: meta.color }} /><div className="flex min-w-0 items-start justify-between gap-2"><div><p className="text-sm font-medium text-text-primary">{event.label}</p><p className="mt-0.5 text-sm text-text-secondary">{event.value}</p></div><span className="shrink-0 rounded-md bg-[#F4F7F6] px-2 py-1 text-[10px]" style={{ color: meta.color }}>{meta.label}</span></div></div>; }) : <div className="grid h-40 place-items-center text-sm text-text-secondary">今天还没有观察记录</div>}
          </div>
        </section>
      </div>

      <button type="button" onClick={() => openSheet("water_ml")} className="fixed bottom-6 right-5 z-30 inline-flex items-center gap-2 rounded-full bg-brand px-5 py-3 text-sm font-medium text-white shadow-[0_14px_35px_rgba(57,123,120,0.3)] hover:bg-brand/90 md:right-8"><Plus size={18} />添加记录</button>
      <AddRecordSheet key={sheetKind} open={sheetOpen} initialKind={sheetKind} onClose={() => setSheetOpen(false)} onSaved={(record) => { setAllObservations((items) => [record, ...items]); setToday((summary) => summary ? { ...summary, observations: [record, ...summary.observations] } : summary); }} />
    </div>
  );
}
