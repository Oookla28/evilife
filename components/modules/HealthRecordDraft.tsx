"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, ClipboardPlus, Save, X } from "lucide-react";
import { addObservations, type ObservationKind } from "@/lib/api/health-profile";
import { ConfirmationCard } from "./SystemModules";

interface DraftItem {
  id: string;
  kind: ObservationKind;
  label: string;
  unit: string;
  value: number;
  source_text: string;
}

const limits: Partial<Record<ObservationKind, { min: number; max: number; step: number }>> = {
  water_ml: { min: 0, max: 10000, step: 50 },
  steps: { min: 0, max: 200000, step: 100 },
  sleep_minutes: { min: 0, max: 1440, step: 5 },
  weight_kg: { min: 1, max: 500, step: 0.1 },
  waist_cm: { min: 1, max: 400, step: 0.1 },
  resting_heart_rate: { min: 20, max: 300, step: 1 },
  mood_score: { min: 1, max: 5, step: 1 },
};

export function HealthRecordDraft({ items }: { action_id: string; items: DraftItem[] }) {
  const [drafts, setDrafts] = useState(items);
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedCount, setSavedCount] = useState(0);
  const [error, setError] = useState("");
  const valid = useMemo(() => drafts.every((item) => {
    const limit = limits[item.kind];
    return Number.isFinite(item.value) && (!limit || (item.value >= limit.min && item.value <= limit.max));
  }), [drafts]);

  const save = async () => {
    if (!drafts.length || !valid) return;
    setSaving(true); setError("");
    try {
      const records = await addObservations(drafts.map((item) => ({ kind: item.kind, value: item.value, source: "self_report" })));
      setSavedCount(records.length); setConfirming(false);
    } catch { setError("记录没有写入，请检查数值后重试。"); }
    finally { setSaving(false); }
  };

  if (savedCount) {
    return <section className="flex items-start gap-3 rounded-2xl border border-brand/20 bg-brand/5 p-5 text-brand"><CheckCircle2 size={24} className="mt-0.5 shrink-0" /><div><h3 className="font-medium">已添加 {savedCount} 条健康记录</h3><p className="mt-1 text-sm text-text-secondary">已保存到实验者健康档案；这些是本人记录，不是 AI 测量值。</p><a href="/profile" className="mt-2 inline-block text-sm font-medium underline underline-offset-4">查看健康档案</a></div></section>;
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-border-divider bg-white shadow-sm" aria-label="待添加健康记录">
      <header className="flex items-start gap-3 border-b border-border-divider bg-[#FAFBFB] px-4 py-4 sm:px-5"><ClipboardPlus size={20} className="mt-0.5 shrink-0 text-brand" /><div><h3 className="font-semibold text-text-primary">发现可添加的健康记录</h3><p className="mt-1 text-xs leading-5 text-text-secondary">请核对或修改数值。确认前不会写入健康档案。</p></div></header>
      <div className="space-y-2 p-4 sm:p-5">
        {drafts.map((item) => { const limit = limits[item.kind]; const outOfRange = !Number.isFinite(item.value) || Boolean(limit && (item.value < limit.min || item.value > limit.max)); return (
          <div key={item.id} className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-xl border border-border-divider px-3 py-3 sm:grid-cols-[130px_1fr_auto]">
            <div className="col-span-2 sm:col-span-1"><p className="text-sm font-medium text-text-primary">{item.label}</p><p className="mt-0.5 max-w-[220px] truncate text-[10px] text-text-secondary" title={item.source_text}>来自“{item.source_text}”</p></div>
            <label className="flex min-w-0 items-center justify-start gap-2"><span className="sr-only">{item.label}数值</span><input type="number" value={Number.isFinite(item.value) ? item.value : ""} min={limit?.min} max={limit?.max} step={limit?.step ?? 1} onChange={(event) => setDrafts((current) => current.map((draft) => draft.id === item.id ? { ...draft, value: event.target.value === "" ? Number.NaN : Number(event.target.value) } : draft))} className={`w-28 rounded-lg border bg-white px-3 py-2 text-right text-sm text-text-primary outline-none focus:ring-2 focus:ring-brand/25 ${outOfRange ? "border-risk-refused" : "border-border-divider"}`} /><span className="min-w-0 text-xs text-text-secondary">{item.unit}</span></label>
            <button type="button" aria-label={`移除${item.label}记录`} onClick={() => setDrafts((current) => current.filter((draft) => draft.id !== item.id))} className="rounded-lg p-2 text-text-secondary hover:bg-black/5 hover:text-risk-refused"><X size={15} /></button>
          </div>
        ); })}
        {!drafts.length ? <p className="py-5 text-center text-sm text-text-secondary">已移除全部待添加记录</p> : null}
        <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs text-text-secondary">一次确认可同时添加 {drafts.length} 条记录</p><button type="button" onClick={() => setConfirming(true)} disabled={!drafts.length || !valid || saving} className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white disabled:opacity-45"><Save size={16} />确认添加</button></div>
        {confirming ? <ConfirmationCard title={`添加这 ${drafts.length} 条健康记录？`} message="将按你核对后的数值写入实验者健康档案。" label={saving ? "保存中…" : "确认并添加"} onCancel={() => setConfirming(false)} onConfirm={() => void save()} /> : null}
        {error ? <p role="alert" className="text-sm text-risk-refused">{error}</p> : null}
      </div>
    </section>
  );
}
