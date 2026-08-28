"use client";

import { useMemo, useState } from "react";
import { Droplets, Footprints, HeartPulse, Moon, NotebookPen, Ruler, Scale, Smile, X } from "lucide-react";
import {
  addObservation,
  type ObservationKind,
  type ObservationRecord,
} from "@/lib/api/health-profile";

const recordTypes = [
  { kind: "water_ml", label: "饮水", unit: "ml", icon: Droplets, placeholder: "例如 300" },
  { kind: "steps", label: "步数", unit: "步", icon: Footprints, placeholder: "例如 5796" },
  { kind: "sleep_minutes", label: "睡眠", unit: "分钟", icon: Moon, placeholder: "例如 440" },
  { kind: "weight_kg", label: "体重", unit: "kg", icon: Scale, placeholder: "例如 69.0" },
  { kind: "waist_cm", label: "腰围", unit: "cm", icon: Ruler, placeholder: "例如 78" },
  { kind: "resting_heart_rate", label: "静息心率", unit: "次/分", icon: HeartPulse, placeholder: "例如 68" },
  { kind: "mood_score", label: "心情", unit: "1–5", icon: Smile, placeholder: "1 到 5" },
  { kind: "note", label: "备注", unit: "", icon: NotebookPen, placeholder: "记录当天影响实验观察的事件" },
] as const;

interface AddRecordSheetProps {
  open: boolean;
  onClose: () => void;
  onSaved: (record: ObservationRecord) => void;
  initialKind?: ObservationKind;
}

export function AddRecordSheet({ open, onClose, onSaved, initialKind = "water_ml" }: AddRecordSheetProps) {
  const [kind, setKind] = useState<ObservationKind>(initialKind);
  const [value, setValue] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const selected = useMemo(() => recordTypes.find((item) => item.kind === kind) ?? recordTypes[0], [kind]);

  if (!open) return null;

  const save = async () => {
    const parsed = Number(value);
    if (kind !== "note" && (!value || !Number.isFinite(parsed) || parsed < 0)) {
      setError("请输入有效的非负数值。");
      return;
    }
    if (kind === "mood_score" && (parsed < 1 || parsed > 5)) {
      setError("心情评分请填写 1 到 5。");
      return;
    }
    if (kind === "note" && !note.trim()) {
      setError("请填写备注内容。");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const record = await addObservation({
        kind,
        value: kind === "note" ? undefined : parsed,
        note: note.trim() || undefined,
        source: "self_report",
      });
      onSaved(record);
      setValue("");
      setNote("");
      onClose();
    } catch {
      setError("记录没有保存，请确认后端服务已启动。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/20 p-0 backdrop-blur-[2px] sm:items-center sm:p-6" role="presentation" onMouseDown={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-record-title"
        onMouseDown={(event) => event.stopPropagation()}
        className="max-h-[92dvh] w-full overflow-y-auto rounded-t-[26px] border border-border-divider bg-white p-5 shadow-[0_28px_90px_rgba(28,42,40,0.18)] sm:max-w-xl sm:rounded-[26px] sm:p-6"
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 id="add-record-title" className="text-xl font-semibold text-text-primary">添加观察记录</h2>
            <p className="mt-1 text-sm text-text-secondary">保存你观察到的事实，不自动生成诊断。</p>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭添加记录" className="rounded-full p-2 text-text-secondary hover:bg-black/5"><X size={19} /></button>
        </div>

        <div className="mt-5 grid grid-cols-4 gap-2" aria-label="记录类型">
          {recordTypes.map((item) => {
            const Icon = item.icon;
            const active = item.kind === kind;
            return (
              <button
                type="button"
                key={item.kind}
                onClick={() => { setKind(item.kind); setError(""); }}
                aria-pressed={active}
                className={`flex min-h-20 flex-col items-center justify-center gap-1.5 rounded-2xl border text-xs transition-colors ${active ? "border-brand bg-brand/[0.08] text-brand" : "border-border-divider text-text-secondary hover:bg-black/[0.025]"}`}
              >
                <Icon size={19} />{item.label}
              </button>
            );
          })}
        </div>

        <div className="mt-5 rounded-2xl bg-[#F7F8F8] p-4">
          <label className="text-sm font-medium text-text-primary" htmlFor="record-value">{selected.label}{selected.unit ? `（${selected.unit}）` : ""}</label>
          {kind === "note" ? (
            <textarea id="record-value" value={note} onChange={(event) => setNote(event.target.value)} placeholder={selected.placeholder} rows={4} className="mt-3 w-full resize-none rounded-xl border border-border-divider bg-white px-3 py-2.5 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/10" />
          ) : (
            <input id="record-value" type="number" min="0" step="any" value={value} onChange={(event) => setValue(event.target.value)} placeholder={selected.placeholder} className="mt-3 w-full rounded-xl border border-border-divider bg-white px-3 py-2.5 text-lg font-medium outline-none focus:border-brand focus:ring-2 focus:ring-brand/10" />
          )}
          {kind !== "note" ? <textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="可选备注，例如测量条件" rows={2} className="mt-3 w-full resize-none rounded-xl border border-border-divider bg-white px-3 py-2.5 text-sm outline-none focus:border-brand" /> : null}
          <p className="mt-3 text-xs text-text-secondary">来源：本人手动记录</p>
        </div>

        {error ? <p role="alert" className="mt-3 text-sm text-risk-refused">{error}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-xl border border-border-divider px-4 py-2.5 text-sm text-text-primary">取消</button>
          <button type="button" onClick={() => void save()} disabled={saving} className="rounded-xl bg-brand px-5 py-2.5 text-sm font-medium text-white disabled:opacity-60">{saving ? "保存中…" : "确认记录"}</button>
        </div>
      </section>
    </div>
  );
}
