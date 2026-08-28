"use client";

import { useMemo, useState } from "react";
import {
  BadgeCheck,
  BookOpenCheck,
  Database,
  ExternalLink,
  Filter,
  Search,
  ShieldCheck,
} from "lucide-react";

const packets = [
  {
    topic: "地中海饮食与心血管结局",
    verdict: "总体支持",
    strength: "较高",
    type: "随机试验 / 系统综述",
    source: "PubMed · Europe PMC",
    note: "长期饮食模式与主要心血管事件相关；效果取决于依从性和基线风险。",
    accent: "support",
  },
  {
    topic: "限制钠摄入与血压",
    verdict: "支持，存在人群差异",
    strength: "中等",
    type: "系统综述 / 指南",
    source: "WHO · PubMed",
    note: "平均血压可下降，但个体反应、用药和肾功能需要共同考虑。",
    accent: "support",
  },
  {
    topic: "限时进食与减重",
    verdict: "未显示明确额外优势",
    strength: "中等",
    type: "随机对照试验",
    source: "PubMed · Europe PMC",
    note: "与等热量限制相比，减重优势并不稳定；研究时长和执行方式差异较大。",
    accent: "boundary",
  },
  {
    topic: "鸡蛋摄入与心血管风险",
    verdict: "证据不一致",
    strength: "有限",
    type: "队列研究 / Meta 分析",
    source: "PubMed",
    note: "观察性证据容易受到整体饮食与生活方式混杂影响，不宜给出绝对数量结论。",
    accent: "boundary",
  },
  {
    topic: "咖啡摄入与长期健康结局",
    verdict: "相关性证据为主",
    strength: "有限",
    type: "观察性研究 / 综述",
    source: "PubMed · Europe PMC",
    note: "部分结局显示有利相关，但不能直接解释为因果；孕期和咖啡因敏感人群需单独判断。",
    accent: "boundary",
  },
  {
    topic: "运动干预与代谢健康",
    verdict: "总体支持",
    strength: "较高",
    type: "指南 / 系统综述",
    source: "WHO · PubMed",
    note: "规律活动通常改善多项代谢指标；处方需匹配年龄、疾病状态和运动风险。",
    accent: "support",
  },
];

export default function LabPage() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "support" | "boundary">("all");
  const visible = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return packets.filter(
      (packet) =>
        (filter === "all" || packet.accent === filter) &&
        (!normalized || `${packet.topic}${packet.verdict}${packet.type}`.toLowerCase().includes(normalized)),
    );
  }, [filter, query]);

  return (
    <div className="h-full overflow-y-auto px-4 py-8 md:px-8">
      <div className="mx-auto w-full max-w-6xl">
        <header className="overflow-hidden rounded-[28px] border border-border-divider bg-[linear-gradient(135deg,#123f36,#1f715d)] px-6 py-7 text-white shadow-[var(--shadow-soft)] md:px-9 md:py-9">
          <div className="flex flex-col justify-between gap-7 md:flex-row md:items-end">
            <div className="max-w-2xl">
              <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-100/80">
                <BookOpenCheck size={15} /> Evidence Library
              </p>
              <h1 className="text-3xl font-bold tracking-tight md:text-4xl">证据实验室</h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-emerald-50/75">
                查看进入回答引擎的权威主张、证据边界和来源血缘。当前库采用结构化摘要，不保存受版权保护的文献全文。
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              {[["33", "可检索主张"], ["10", "权威来源"], ["6", "主题包"]].map(([value, label]) => (
                <div key={label} className="min-w-20 rounded-2xl border border-white/10 bg-white/8 px-3 py-3 backdrop-blur">
                  <strong className="block text-xl">{value}</strong><span className="text-[10px] text-emerald-50/65">{label}</span>
                </div>
              ))}
            </div>
          </div>
        </header>

        <section className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            [Database, "双层数据库", "医学证据只读、用户数据可写，避免业务数据污染证据语料。"],
            [ShieldCheck, "双向检索", "同时寻找支持证据与反对/边界证据，减少单边确认偏误。"],
            [BadgeCheck, "主张级引用", "结论关联具体来源、研究类型、适用人群与局限，不只列参考文献。"],
          ].map(([Icon, title, body]) => {
            const FeatureIcon = Icon as typeof Database;
            return (
              <article key={title as string} className="rounded-2xl border border-border-divider bg-white p-5 shadow-sm">
                <FeatureIcon className="text-brand" size={20} />
                <h2 className="mt-4 text-sm font-semibold text-text-primary">{title as string}</h2>
                <p className="mt-2 text-xs leading-5 text-text-secondary">{body as string}</p>
              </article>
            );
          })}
        </section>

        <div className="mt-7 flex flex-col gap-3 sm:flex-row">
          <label className="flex flex-1 items-center gap-3 rounded-2xl border border-border-divider bg-white px-4 py-3 shadow-sm">
            <Search size={18} className="text-text-secondary" />
            <span className="sr-only">搜索证据主题</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索主题、结论或研究类型" className="w-full bg-transparent text-sm outline-none placeholder:text-text-secondary/60" />
          </label>
          <div className="flex items-center gap-1 rounded-2xl border border-border-divider bg-white p-1.5 shadow-sm" aria-label="筛选证据结论">
            <Filter size={15} className="mx-2 text-text-secondary" />
            {(["all", "support", "boundary"] as const).map((value) => (
              <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)} className="rounded-xl px-3 py-2 text-xs text-text-secondary aria-pressed:bg-brand aria-pressed:text-white">
                {value === "all" ? "全部" : value === "support" ? "支持" : "边界/不一致"}
              </button>
            ))}
          </div>
        </div>

        <section className="mt-4 grid gap-4 pb-10 lg:grid-cols-2">
          {visible.map((packet) => (
            <article key={packet.topic} className="group rounded-2xl border border-border-divider bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-soft)]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ${packet.accent === "support" ? "bg-emerald-50 text-evidence-support" : "bg-amber-50 text-evidence-boundary"}`}>{packet.verdict}</span>
                  <h2 className="mt-3 text-base font-semibold text-text-primary">{packet.topic}</h2>
                </div>
                <ExternalLink size={16} className="mt-1 text-text-secondary/45" />
              </div>
              <p className="mt-3 text-sm leading-6 text-text-secondary">{packet.note}</p>
              <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-border-divider pt-4 text-[11px] text-text-secondary">
                <span><strong className="text-text-primary">证据强度：</strong>{packet.strength}</span>
                <span><strong className="text-text-primary">研究类型：</strong>{packet.type}</span>
                <span><strong className="text-text-primary">来源：</strong>{packet.source}</span>
              </div>
            </article>
          ))}
        </section>
      </div>
    </div>
  );
}
