"use client";

import { useEffect, useRef, useState } from "react";
import { Cable, Camera, FileUp, LoaderCircle } from "lucide-react";
import { ComprehensiveHealthCard } from "@/components/health-profile/ComprehensiveHealthCard";
import { analyzeHealthProfile, getAppleHealthImport, getHealthConnectors, startAppleHealthImport, type HealthConnector, type ProfileAnalysisResponse } from "@/lib/api/health-profile";
import { getTodayRecords, type TodayRecords } from "@/lib/api/today";

type Feature = "health_profile_analysis" | "today_review" | "apple_health_import" | "health_connectors" | "meal_photo";

export function ChatFeaturePanel({ feature, title }: { feature: Feature; title?: string }) {
  const [analysis, setAnalysis] = useState<ProfileAnalysisResponse | null>(null);
  const [today, setToday] = useState<TodayRecords | null>(null);
  const [connectors, setConnectors] = useState<HealthConnector[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    if (feature === "health_profile_analysis") analyzeHealthProfile().then((value) => { if (!cancelled) setAnalysis(value); }).catch(() => { if (!cancelled) setError("综合分析暂时不可用，请稍后重试。"); });
    if (feature === "today_review") getTodayRecords(new Date().toISOString().slice(0, 10)).then((value) => { if (!cancelled) setToday(value); }).catch(() => { if (!cancelled) setError("今日记录暂时不可用。"); });
    if (feature === "health_connectors" || feature === "apple_health_import") getHealthConnectors().then((value) => { if (!cancelled) setConnectors(value); }).catch(() => { if (!cancelled) setError("健康软件连接器暂时不可用。"); });
    return () => { cancelled = true; };
  }, [feature]);

  const importApple = async (file: File) => {
    setError(""); setStatus("正在上传并流式解析…");
    try { let job = await startAppleHealthImport(file); while (job.status === "queued" || job.status === "running") { setStatus(`已检查 ${job.processed_records.toLocaleString()} 条原始记录…`); await new Promise((resolve) => window.setTimeout(resolve, 750)); job = await getAppleHealthImport(job.id); } if (job.status !== "completed" || !job.summary) throw new Error(job.error || "导入失败"); setStatus(`导入完成：新增 ${job.summary.accepted} 条每日汇总，跳过 ${job.summary.skipped} 条重复。`); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "导入失败"); setStatus(""); }
  };

  if (feature === "health_profile_analysis") return <div>{analysis?.cards[0] ? <ComprehensiveHealthCard card={analysis.cards[0]} source={analysis.source} /> : error ? <p role="alert" className="text-sm text-risk-refused">{error}</p> : <p className="flex items-center gap-2 text-sm text-text-secondary"><LoaderCircle size={16} className="animate-spin" />正在结合已保存的身体记录生成综合分析…</p>}</div>;
  if (feature === "today_review") return <section className="rounded-[20px] border border-border-divider bg-white p-5"><h3 className="text-base font-semibold text-text-primary">{title ?? "今日记录"}</h3>{today ? <div className="mt-4 grid grid-cols-3 gap-2 text-center"><div className="rounded-xl bg-bg-page p-3"><strong className="block text-xl">{today.observations.length}</strong><span className="text-xs text-text-secondary">健康记录</span></div><div className="rounded-xl bg-bg-page p-3"><strong className="block text-xl">{today.meals.length}</strong><span className="text-xs text-text-secondary">餐食</span></div><div className="rounded-xl bg-bg-page p-3"><strong className="block text-xl">{today.fasts.length}</strong><span className="text-xs text-text-secondary">进食间隔</span></div></div> : <p className="mt-3 text-sm text-text-secondary">正在读取今天的数据…</p>}</section>;
  if (feature === "meal_photo") return <section className="rounded-[20px] border border-[#E7DDD6] bg-[#FCF9F7] p-5"><div className="flex items-center gap-2"><Camera size={19} className="text-[#9A6547]" /><h3 className="font-semibold">餐食图片识别</h3></div><p className="mt-2 text-sm leading-6 text-text-secondary">直接把餐食照片粘贴或拖入当前输入框并发送，我会在这段对话中识别食物、估计份量和热量区间。</p></section>;
  return <section className="rounded-[20px] border border-border-divider bg-white p-5"><div className="flex items-center gap-2">{feature === "apple_health_import" ? <FileUp size={19} className="text-brand" /> : <Cable size={19} className="text-brand" />}<h3 className="font-semibold text-text-primary">{title}</h3></div>{feature === "apple_health_import" ? <><input ref={inputRef} type="file" accept=".xml,text/xml,application/xml" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (file) void importApple(file); }} /><button type="button" onClick={() => inputRef.current?.click()} className="mt-4 rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white">选择 Apple 健康导出 XML</button></> : <div className="mt-3 space-y-2">{connectors.map((item) => <div key={item.id} className="rounded-xl bg-bg-page p-3"><p className="text-sm font-medium">{item.label}</p><p className="mt-1 text-xs leading-5 text-text-secondary">{item.authorization}</p></div>)}</div>}{status ? <p role="status" className="mt-3 text-xs text-brand">{status}</p> : null}{error ? <p role="alert" className="mt-3 text-xs text-risk-refused">{error}</p> : null}</section>;
}
