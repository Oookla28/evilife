"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Camera, FileScan, LoaderCircle, ShieldCheck, Upload } from "lucide-react";
import { analyzeReport, type ReportAnalysis } from "@/lib/api/reports";

export function ReportAnalysisPanel() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<ReportAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (file?: File) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      setResult(await analyzeReport(file));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "报告分析失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mt-6 grid gap-3 lg:grid-cols-[1.35fr_0.65fr]">
      <div className="rounded-[22px] border border-border-divider bg-white p-5 shadow-[0_12px_35px_rgba(35,50,48,0.035)] sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div><p className="text-xs font-medium uppercase tracking-[0.18em] text-brand">Medical report</p><h2 className="mt-2 text-lg font-semibold text-text-primary">体检报告智能解读</h2><p className="mt-1 text-sm leading-6 text-text-secondary">上传 PDF、图片或文本，结构化整理指标并保留原报告边界。</p></div>
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-brand/10 text-brand"><FileScan size={22} /></span>
        </div>
        <input ref={inputRef} className="hidden" type="file" accept=".pdf,.txt,.csv,image/jpeg,image/png,image/webp" onChange={(event) => void submit(event.target.files?.[0])} />
        <button type="button" onClick={() => inputRef.current?.click()} disabled={busy} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
          {busy ? <LoaderCircle size={17} className="animate-spin" /> : <Upload size={17} />}{busy ? "正在安全分析…" : "选择体检报告"}
        </button>
        {error ? <p role="alert" className="mt-3 text-sm text-risk-refused">{error}</p> : null}
        {result ? <div className="mt-5 rounded-2xl bg-[#F5F8F7] p-4"><p className="font-medium text-text-primary">{result.summary}</p><div className="mt-3 grid gap-2 sm:grid-cols-2">{result.items.slice(0, 8).map((item, index) => <div key={`${item.name}-${index}`} className="rounded-xl bg-white px-3 py-2 text-sm"><div className="flex justify-between gap-2"><span className="font-medium text-text-primary">{item.name}</span><span className={item.flag === "high" || item.flag === "low" ? "text-risk-refused" : "text-brand"}>{item.value} {item.unit}</span></div><p className="mt-1 text-xs text-text-secondary">参考：{item.reference_range || "以原报告为准"}</p></div>)}</div><p className="mt-3 flex items-start gap-2 text-xs leading-5 text-text-secondary"><ShieldCheck size={14} className="mt-0.5 shrink-0" />自动识别需逐项核对，不提供诊断或用药建议。</p></div> : null}
      </div>
      <div className="rounded-[22px] border border-[#CFE4E0] bg-[linear-gradient(145deg,#F1FAF8,#EEF5FF)] p-5 sm:p-6">
        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-white text-brand shadow-sm"><Camera size={22} /></span>
        <h2 className="mt-5 text-lg font-semibold text-text-primary">拍照识别餐食热量</h2>
        <p className="mt-2 text-sm leading-6 text-text-secondary">识别食物、份量和烹饪方式，给出区间估算与不确定性，不把估算伪装成精确值。</p>
        <Link href="/?tool=meal" className="mt-5 inline-flex rounded-xl border border-brand/20 bg-white px-4 py-2.5 text-sm font-medium text-brand">打开相机 / 上传照片</Link>
        <p className="mt-3 text-xs leading-5 text-text-secondary">视觉服务使用独立部署的 DeepSeek‑VL2 Small；普通 DeepSeek 文本接口不接收图片。</p>
      </div>
    </section>
  );
}
