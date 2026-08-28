"use client";

import { useMemo, useState } from "react";
import { AlertCircle, Camera, Save, Edit3, CheckCircle2, Gauge } from "lucide-react";
import { confirmAction } from "@/lib/api/actions";
import { ConfirmationCard } from "./SystemModules";

export interface MealItem {
  id: string;
  name: string;
  portion: string;
  portion_grams?: [number, number];
  estimated_calories: [number, number]; // [min, max]
  estimated_calories_center?: number;
  confidence?: "low" | "medium" | "high";
  reference_basis?: string;
  uncertainty?: string;
}

export interface MealAnalyzerProps {
  action_id: string;
  image_url?: string;
  items: MealItem[];
  total_calories: [number, number];
  total_calories_center?: number;
  status: string;
  overall_uncertainty?: string;
  analysis_error?: string;
}

const confidenceLabel = { low: "低置信", medium: "中等置信", high: "较高置信" } as const;

function calorieCenter(item: MealItem) {
  return item.estimated_calories_center ?? Math.round((item.estimated_calories[0] + item.estimated_calories[1]) / 2);
}

export function MealAnalyzer({ action_id, image_url, items, total_calories, total_calories_center, overall_uncertainty, analysis_error }: MealAnalyzerProps) {
  const [editedItems, setEditedItems] = useState(items);
  const [isEditing, setIsEditing] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [saveError, setSaveError] = useState("");
  const editedTotal = useMemo<[number, number]>(() => {
    if (editedItems.length === 0) return total_calories;
    return editedItems.reduce(
      (total, item) => [
        total[0] + item.estimated_calories[0],
        total[1] + item.estimated_calories[1],
      ] as [number, number],
      [0, 0] as [number, number]
    );
  }, [editedItems, total_calories]);
  const editedTotalCenter = useMemo(
    () => editedItems.length ? editedItems.reduce((sum, item) => sum + calorieCenter(item), 0) : (total_calories_center ?? Math.round((total_calories[0] + total_calories[1]) / 2)),
    [editedItems, total_calories, total_calories_center]
  );
  
  const handleSave = async () => {
    setIsSaving(true);
    setSaveError("");
    try {
      await confirmAction(action_id, {
        run_id: "current-run",
        confirmed: true,
        client_action_id: action_id,
        edited_items: editedItems,
        estimated_total_calories: editedTotal,
        estimated_total_calories_center: editedTotalCenter,
      });
      setSaved(true);
    } catch {
      setSaveError("保存失败，记录没有写入，请稍后重试。");
    } finally {
      setIsSaving(false);
      setConfirming(false);
    }
  };

  const handleEditPortion = (id: string, newPortion: string) => {
    setEditedItems(prev => prev.map(item => {
      if (item.id !== id) return item;
      const grams = Number(newPortion.match(/(\d+(?:\.\d+)?)\s*(?:g|克)/i)?.[1]);
      const originalGrams = item.portion_grams
        ? (item.portion_grams[0] + item.portion_grams[1]) / 2
        : Number(item.portion.match(/(\d+(?:\.\d+)?)\s*(?:g|克)/i)?.[1]);
      if (!Number.isFinite(grams) || grams <= 0 || !Number.isFinite(originalGrams) || originalGrams <= 0) {
        return { ...item, portion: newPortion };
      }
      const ratio = grams / originalGrams;
      const range: [number, number] = [
        Math.max(1, Math.round(item.estimated_calories[0] * ratio)),
        Math.max(1, Math.round(item.estimated_calories[1] * ratio)),
      ];
      return {
        ...item,
        portion: newPortion,
        portion_grams: [Math.round(grams), Math.round(grams)],
        estimated_calories: range,
        estimated_calories_center: Math.max(range[0], Math.min(range[1], Math.round(calorieCenter(item) * ratio))),
      };
    }));
    setIsEditing(null);
  };

  if (saved) {
    return (
      <div className="bg-brand/5 border border-brand/20 p-5 rounded-2xl flex flex-col items-center justify-center gap-2 text-brand">
        <CheckCircle2 size={32} />
          <h3 className="font-medium text-lg">餐食已写入今日记录</h3>
          <p className="text-sm opacity-80">保存的是你确认后的食物和估算范围，不是精确营养测量。</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-border-divider rounded-2xl shadow-sm overflow-hidden">
      <div className="p-4 border-b border-border-divider bg-bg-page/50 flex items-center gap-3">
        <Camera className="text-text-secondary" size={20} />
        <h3 className="font-semibold text-text-primary">餐食成分识别</h3>
      </div>
      
      <div className="p-5 flex flex-col gap-4">
        {image_url && (
          <div className="w-full h-48 bg-black/5 rounded-xl overflow-hidden relative">
            {/* Using next/image or standard img in real app */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={image_url} alt="Meal" className="w-full h-full object-cover" />
          </div>
        )}

        <div className="flex justify-between items-end mb-2">
          <div className="text-sm text-text-secondary">识别包含以下成分，您可以修正分量：</div>
        </div>

        {analysis_error ? (
          <div role="alert" className="flex items-start gap-3 rounded-xl border border-risk-refused/20 bg-risk-refused/5 p-4 text-sm text-text-primary">
            <AlertCircle className="mt-0.5 shrink-0 text-risk-refused" size={18} />
            <div>
              <p className="font-medium">这次没有识别出有效餐食</p>
              <p className="mt-1 text-text-secondary">{analysis_error}</p>
            </div>
          </div>
        ) : null}

        <div className="flex flex-col gap-3">
          {editedItems.map(item => (
            <div key={item.id} className="p-3 border border-border-divider rounded-xl hover:border-brand/30 transition-colors">
              <div className="flex justify-between items-start">
                <div className="flex flex-col">
                  <span className="font-medium text-text-primary">{item.name}</span>
                  <span className="mt-0.5 text-base font-semibold text-text-primary">约 {calorieCenter(item)} kcal</span>
                  <span className="text-xs text-text-secondary">合理范围 {item.estimated_calories[0]}–{item.estimated_calories[1]} kcal</span>
                </div>
                
                {isEditing === item.id ? (
                  <div className="flex items-center gap-2">
                    <input 
                      type="text" 
                      aria-label={`修改${item.name}分量`}
                      defaultValue={item.portion}
                      className="border border-brand rounded px-2 py-1 text-sm w-24 outline-none"
                      onBlur={(e) => handleEditPortion(item.id, e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleEditPortion(item.id, e.currentTarget.value)}
                      autoFocus
                    />
                  </div>
                ) : (
                  <button 
                    onClick={() => setIsEditing(item.id)}
                    className="flex items-center gap-1 text-sm text-text-secondary hover:text-brand bg-bg-page px-2 py-1 rounded transition-colors"
                  >
                    <span>{item.portion}</span>
                    <Edit3 size={12} />
                  </button>
                )}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-text-secondary">
                {item.portion_grams ? <span>估计可食重量 {item.portion_grams[0]}–{item.portion_grams[1]} g</span> : null}
                {item.confidence ? <span className="inline-flex items-center gap-1 rounded-full bg-bg-page px-2 py-1"><Gauge size={11} />{confidenceLabel[item.confidence]}</span> : null}
              </div>
              {item.reference_basis ? <p className="mt-2 text-xs leading-5 text-text-secondary">换算依据：{item.reference_basis}</p> : null}
              {item.uncertainty && (
                <div className="mt-2 text-xs text-evidence-boundary bg-evidence-boundary/5 p-2 rounded">
                  {item.uncertainty}
                </div>
              )}
            </div>
          ))}
        </div>

        {!analysis_error && editedItems.length > 0 ? <div className="mt-4 p-4 bg-bg-page rounded-xl flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-center">
          <div className="flex flex-col">
            <span className="text-sm text-text-secondary">总计估算热量</span>
            <span className="text-xl font-bold text-text-primary">
              约 {editedTotalCenter} kcal
            </span>
            <span className="text-xs text-text-secondary">合理范围 {editedTotal[0]}–{editedTotal[1]} kcal</span>
          </div>
          <button 
            onClick={() => setConfirming(true)}
            disabled={isSaving}
            className="bg-brand text-white px-5 py-2 rounded-xl hover:bg-brand/90 transition-colors font-medium flex items-center gap-2 disabled:opacity-70"
          >
            {isSaving ? "保存中..." : <><Save size={18} /> 确认并保存</>}
          </button>
        </div> : null}
        {confirming ? (
          <ConfirmationCard
            title="保存这次餐食记录？"
            message="将按你修正后的分量保存估算范围；保存前不会写入今日记录。"
            label={isSaving ? "保存中..." : "确认并保存"}
            onCancel={() => setConfirming(false)}
            onConfirm={() => void handleSave()}
          />
        ) : null}
        {saveError ? <p role="alert" className="text-sm text-risk-refused">{saveError}</p> : null}
        {!analysis_error && editedItems.length > 0 ? <p className="text-xs text-text-secondary text-center">
          注：中心值来自多模态模型对食物、烹饪方式和份量的联合估计，不是精确测量；输入“150g”一类分量可按重量重新换算。{overall_uncertainty ? ` ${overall_uncertainty}` : ""}
        </p> : null}
      </div>
    </div>
  );
}
