"use client";

import { Activity, ShieldCheck, TriangleAlert } from "lucide-react";
import type { ProfileAnalysisCard } from "@/lib/api/health-profile";

export function ComprehensiveHealthCard({ card, source }: { card: ProfileAnalysisCard; source?: "ai" | "deterministic_fallback" }) {
  return (
    <article className="overflow-hidden rounded-[24px] border border-[#DEE1EA] bg-white shadow-[0_18px_55px_rgba(56,66,104,0.09)]">
      <div className="border-b border-[#E5E6EC] bg-[linear-gradient(120deg,#F0F2F8_0%,#FFFFFF_68%)] px-5 py-5 sm:px-7">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[#536AA6] text-white"><Activity size={21} /></span>
          <div><h3 className="text-lg font-semibold text-[#1D2927]">{card.title}</h3><p className="mt-1 text-sm leading-6 text-[#61706D]">{card.preview}</p></div>
        </div>
      </div>
      <div className="grid gap-3 p-5 sm:grid-cols-2 sm:p-7">
        {card.details.map((detail) => {
          const attention = detail.label.includes("关注") || detail.label.includes("就医");
          return <section key={detail.label} className={`rounded-2xl border p-4 ${attention ? "border-[#E8CCD2] bg-[#FCF5F7]" : "border-[#E4E6ED] bg-[#FAFAFC]"}`}>
            <div className={`flex items-center gap-2 text-xs font-semibold ${attention ? "text-[#B95767]" : "text-[#536AA6]"}`}>{attention ? <TriangleAlert size={14} /> : <ShieldCheck size={14} />}{detail.label}</div>
            <p className="mt-2 text-sm leading-6 text-[#303A38]">{detail.value}</p>
          </section>;
        })}
      </div>
      <p className="border-t border-[#E5ECEA] px-5 py-3 text-[11px] text-[#7A8583] sm:px-7">{source === "ai" ? "AI 基于已保存的非文本健康记录综合整理" : "AI 暂不可用，当前为本地规则综合整理"} · 不能替代医生诊断</p>
    </article>
  );
}
