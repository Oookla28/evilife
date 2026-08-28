"use client";

import { useMemo, useState } from "react";
import { CalendarDays, Database } from "lucide-react";
import type { MedicalFlowCard } from "@/lib/evidence/build-medical-flow-cards";

type Trend = NonNullable<MedicalFlowCard["trend"]>;
type RangeKey = "day" | "week" | "month" | "half" | "year" | "all";
type Point = { key: string; date: Date; label: string; value: number; count: number };

const ranges: Array<{ key: RangeKey; label: string }> = [
  { key: "day", label: "日" }, { key: "week", label: "周" }, { key: "month", label: "月" },
  { key: "half", label: "半年" }, { key: "year", label: "年" }, { key: "all", label: "全部" },
];

function dateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function startOfWeek(date: Date) {
  const copy = new Date(date); copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7)); copy.setHours(0, 0, 0, 0); return copy;
}

function cutoff(range: RangeKey, newest: Date) {
  const value = new Date(newest);
  if (range === "day") value.setDate(value.getDate() - 13);
  if (range === "week") value.setDate(value.getDate() - 6);
  if (range === "month") value.setDate(value.getDate() - 30);
  if (range === "half") value.setMonth(value.getMonth() - 6);
  if (range === "year") value.setFullYear(value.getFullYear() - 1);
  if (range === "all") value.setFullYear(1900);
  value.setHours(0, 0, 0, 0); return value;
}

function bucketKey(date: Date, range: RangeKey) {
  if (range === "half") return dateKey(startOfWeek(date));
  if (range === "year") return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  if (range === "all") return String(date.getFullYear());
  return dateKey(date);
}

function aggregate(trend: Trend, range: RangeKey): Point[] {
  const raw = trend.points.map((point) => ({ ...point, parsed: new Date(point.date) })).sort((a, b) => a.parsed.getTime() - b.parsed.getTime());
  if (!raw.length) return [];
  const start = cutoff(range, raw.at(-1)!.parsed); const buckets = new Map<string, { sum: number; count: number; date: Date }>();
  raw.forEach((point) => { if (point.parsed < start) return; const key = bucketKey(point.parsed, range); const current = buckets.get(key) ?? { sum: 0, count: 0, date: point.parsed }; current.sum += point.value; current.count += 1; current.date = point.parsed; buckets.set(key, current); });
  return [...buckets.entries()].map(([key, item]) => ({ key, date: item.date, value: item.sum / item.count, count: item.count, label: range === "all" ? `${key}年` : range === "year" ? `${item.date.getMonth() + 1}月` : `${item.date.getMonth() + 1}/${item.date.getDate()}` }));
}

function format(value: number, trend: Trend) {
  const fraction = ["kg", "cm"].includes(trend.unit) ? 1 : 0;
  return `${value.toLocaleString("zh-CN", { minimumFractionDigits: fraction, maximumFractionDigits: fraction })} ${trend.unit}`;
}

export function TrendSparkline({ trend }: { trend: Trend }) {
  const values = trend.points.slice(-16).map((point) => point.value); if (values.length < 2) return null;
  const max = Math.max(...values); const min = Math.min(...values); const span = Math.max(1, max - min);
  const path = values.map((value, index) => `${index ? "L" : "M"}${index * (100 / (values.length - 1))},${24 - (value - min) / span * 20}`).join(" ");
  return <div className="mb-2 rounded-lg bg-[#F7F9F8] px-2 py-1.5"><svg viewBox="0 0 100 28" className="h-8 w-full" aria-hidden="true"><path d={path} fill="none" stroke={trend.color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg><p className="text-center text-[8px] text-[#86868B]">放大查看日、月、年趋势</p></div>;
}

export function MedicalCardTrendPanel({ trend }: { trend: Trend }) {
  const [range, setRange] = useState<RangeKey>("month"); const [selected, setSelected] = useState<number | null>(null);
  const points = useMemo(() => aggregate(trend, range), [trend, range]);
  const average = points.length ? points.reduce((sum, point) => sum + point.value, 0) / points.length : 0;
  const highest = points.length ? Math.max(...points.map((point) => point.value)) : 0;
  const width = 760; const height = 260; const left = 50; const right = 28; const top = 24; const bottom = 42;
  const max = Math.max(1, ...points.map((point) => point.value)) * 1.12; const min = trend.chart === "bar" ? 0 : Math.min(...points.map((point) => point.value)) * .98; const span = Math.max(1, max - min);
  const x = (index: number) => left + index * ((width - left - right) / Math.max(1, points.length - 1)); const y = (value: number) => top + (max - value) / span * (height - top - bottom);
  const line = points.map((point, index) => `${index ? "L" : "M"}${x(index)},${y(point.value)}`).join(" "); const active = selected == null ? null : points[selected];
  const sources = trend.points.reduce<Record<string, number>>((all, point) => { const source = point.source ?? "已记录数据"; all[source] = (all[source] ?? 0) + 1; return all; }, {}); const sourceTotal = Math.max(1, Object.values(sources).reduce((a, b) => a + b, 0));
  return <section className="py-5" aria-label={`${trend.label}具体趋势`}>
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-[11px] text-[#86868B]">具体数据趋势</p><h4 className="mt-0.5 text-base font-semibold text-[#1D1D1F]">{trend.label}</h4></div><div className="flex overflow-x-auto rounded-lg bg-[#F1F2F2] p-0.5" role="tablist">{ranges.map((item) => <button key={item.key} type="button" role="tab" aria-selected={range === item.key} onClick={() => setRange(item.key)} className={`min-w-[38px] rounded-md px-2 py-1.5 text-[11px] sm:min-w-[46px] sm:px-2.5 ${range === item.key ? "bg-white font-medium text-[#1D1D1F] shadow-sm" : "text-[#6E6E73]"}`}>{item.label}</button>)}</div></div>
    <div className="relative mt-3 overflow-hidden rounded-xl border border-[#E8E8ED] bg-white" onPointerLeave={() => setSelected(null)}>{points.length ? <svg viewBox={`0 0 ${width} ${height}`} className="h-[230px] w-full sm:h-[270px]" role="img" aria-label={`${trend.label}折线变化图`}>
      {[0, .25, .5, .75, 1].map((ratio) => { const value = min + (max - min) * (1 - ratio); const py = top + ratio * (height - top - bottom); return <g key={ratio}><line x1={left} x2={width - right} y1={py} y2={py} stroke="#E9ECEB" strokeDasharray="4 5"/><text x={left - 8} y={py + 4} textAnchor="end" fontSize="10" fill="#86868B">{Math.round(value).toLocaleString()}</text></g>; })}
      <line x1={left} x2={width - right} y1={y(average)} y2={y(average)} stroke={trend.color} strokeOpacity=".5" strokeDasharray="6 5"/>
      {trend.chart === "bar" ? points.map((point, index) => <rect key={point.key} x={x(index) - Math.max(3, Math.min(9, 230 / points.length))} y={y(point.value)} width={Math.max(6, Math.min(18, 460 / points.length))} height={height - bottom - y(point.value)} rx="4" fill={trend.color} opacity={selected == null || selected === index ? .9 : .32}/>) : <><path d={line} fill="none" stroke={trend.color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>{points.map((point, index) => <circle key={point.key} cx={x(index)} cy={y(point.value)} r={selected === index ? 5 : 3.5} fill="white" stroke={trend.color} strokeWidth="2.5"/>)}</>}
      {points.map((point, index) => <rect key={`hit-${point.key}`} x={x(index) - Math.max(8, 340 / points.length)} y={top} width={Math.max(16, 680 / points.length)} height={height - top - bottom} fill="transparent" onPointerEnter={() => setSelected(index)} onPointerDown={() => setSelected(index)}/>)}
      {points.filter((_, index) => index === 0 || index === points.length - 1 || index % Math.max(1, Math.ceil(points.length / 5)) === 0).map((point) => { const index = points.indexOf(point); return <text key={`axis-${point.key}`} x={x(index)} y={height - 16} textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"} fontSize="10" fill="#86868B">{point.label}</text>; })}
      {selected != null ? <line x1={x(selected)} x2={x(selected)} y1={top} y2={height - bottom} stroke={trend.color} strokeOpacity=".4"/> : null}
    </svg> : <div className="grid h-[230px] place-items-center text-xs text-[#86868B]">当前范围没有记录</div>}{active ? <div className="pointer-events-none absolute left-1/2 top-2 -translate-x-1/2 rounded-lg border border-[#E1E1E6] bg-white/95 px-3 py-2 text-[10px] shadow-lg"><p className="text-[#86868B]">{active.date.toLocaleDateString("zh-CN")}</p><p className="mt-0.5 font-semibold text-[#1D1D1F]">{format(active.value, trend)}</p></div> : null}</div>
    <div className="mt-3 grid grid-cols-3 gap-2">{[{ label: "平均值", value: format(average, trend) }, { label: "最高值", value: format(highest, trend) }, { label: "记录天数", value: `${points.reduce((sum, point) => sum + point.count, 0)} 天` }].map((item) => <div key={item.label} className="rounded-xl bg-[#F7F9F8] px-3 py-2.5"><p className="text-[9px] text-[#86868B]">{item.label}</p><p className="mt-1 text-xs font-semibold text-[#1D1D1F]">{item.value}</p></div>)}</div>
    <div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-xl border border-[#E8E8ED] p-3"><div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#1D1D1F]"><Database size={13} style={{ color: trend.color }}/>数据来源</div>{Object.entries(sources).map(([source, count]) => <div key={source} className="mt-3"><div className="flex justify-between text-[10px] text-[#6E6E73]"><span>{source}</span><span>{Math.round(count / sourceTotal * 100)}%</span></div><div className="mt-1 h-1 rounded-full bg-[#E9ECEB]"><div className="h-full rounded-full" style={{ width: `${count / sourceTotal * 100}%`, backgroundColor: trend.color }}/></div></div>)}</div><div className="rounded-xl border border-[#E8E8ED] p-3"><div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#1D1D1F]"><CalendarDays size={13} style={{ color: trend.color }}/>最近数据</div>{trend.points.slice(-4).reverse().map((point) => <div key={point.date} className="mt-2 flex justify-between text-[10px]"><span className="text-[#6E6E73]">{new Date(point.date).toLocaleDateString("zh-CN")}</span><span className="font-medium text-[#1D1D1F]">{format(point.value, trend)}</span></div>)}</div></div>
  </section>;
}
