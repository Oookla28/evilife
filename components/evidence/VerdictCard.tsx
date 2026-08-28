"use client";

import { useMemo } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleSlash2,
  HelpCircle,
  RefreshCw,
  Scale,
  XCircle,
} from "lucide-react";
import type { VerdictEvidenceItem } from "@/lib/api/types";

export interface VerdictProps {
  verdict: "true" | "partly_true" | "false" | "insufficient";
  confidence: number;
  evidence_grade: "high" | "moderate" | "low" | "insufficient";
  claim: string;
  short_reason: string;
  applies_to: string[];
  does_not_apply_to: string[];
  supporting_evidence: VerdictEvidenceItem[];
  opposing_evidence: VerdictEvidenceItem[];
  uncertainty: string[];
  last_updated: string;
  verdict_detail?:
    | "SUPPORTED"
    | "MOSTLY_SUPPORTED"
    | "CONTEXT_DEPENDENT"
    | "MIXED_EVIDENCE"
    | "NOT_SUPPORTED"
    | "INSUFFICIENT_EVIDENCE";
  what_could_change_this_verdict?: string[];
}

const verdictMeta: Record<
  VerdictProps["verdict"],
  { label: string; icon: typeof CheckCircle2; className: string; bar: string }
> = {
  true: {
    label: "是",
    icon: CheckCircle2,
    className:
      "border-evidence-support/30 bg-evidence-support/10 text-evidence-support",
    bar: "bg-evidence-support",
  },
  partly_true: {
    label: "部分正确",
    icon: Scale,
    className:
      "border-evidence-boundary/30 bg-evidence-boundary/10 text-evidence-boundary",
    bar: "bg-evidence-boundary",
  },
  false: {
    label: "否",
    icon: XCircle,
    className: "border-risk-refused/30 bg-risk-refused/10 text-risk-refused",
    bar: "bg-risk-refused",
  },
  insufficient: {
    label: "证据不足",
    icon: CircleSlash2,
    className: "border-border-divider bg-bg-page/60 text-text-secondary",
    bar: "bg-text-secondary/50",
  },
};

const gradeLabels: Record<VerdictProps["evidence_grade"], string> = {
  high: "高强度证据",
  moderate: "中等强度证据",
  low: "低强度证据",
  insufficient: "证据不足",
};

const detailLabels: Record<NonNullable<VerdictProps["verdict_detail"]>, string> = {
  SUPPORTED: "有证据支持",
  MOSTLY_SUPPORTED: "大体支持",
  CONTEXT_DEPENDENT: "视人群/条件而定",
  MIXED_EVIDENCE: "证据冲突",
  NOT_SUPPORTED: "不支持",
  INSUFFICIENT_EVIDENCE: "证据不足",
};

export function VerdictCard({ verdict }: { verdict: VerdictProps }) {
  const meta = verdictMeta[verdict.verdict];
  const Icon = meta.icon;
  const confidencePercent = Math.round(verdict.confidence * 100);

  const supportingCount = useMemo(
    () => verdict.supporting_evidence.length,
    [verdict.supporting_evidence]
  );
  const opposingCount = useMemo(
    () => verdict.opposing_evidence.length,
    [verdict.opposing_evidence]
  );

  return (
    <section
      aria-label="证据裁决摘要"
      data-testid="verdict-summary"
      className="overflow-hidden rounded-2xl border border-border-divider bg-white"
    >
      <div className="flex flex-col gap-3 border-b border-border-divider p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-11 w-11 items-center justify-center rounded-2xl border ${meta.className}`}
          >
            <Icon size={22} />
          </span>
          <div>
            <p className="flex items-center gap-2 text-sm font-medium text-text-secondary">
              最终裁决
              <span className={`rounded px-1.5 py-0.5 text-xs font-bold ${meta.className}`}>
                {meta.label}
              </span>
            </p>
            <p className="mt-0.5 text-xs text-text-secondary">
              {meta.label === "是"
                ? "该主张得到可追溯证据支持"
                : meta.label === "部分正确"
                  ? "该主张仅在部分人群或条件下成立"
                  : meta.label === "否"
                    ? "现有证据不支持该主张"
                    : "当前证据不足以作出判断"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 sm:flex-col sm:items-end sm:gap-1">
          <p className="font-mono text-lg font-bold text-text-primary">
            {confidencePercent}%
          </p>
          <p className="text-[11px] text-text-secondary">置信度</p>
        </div>
      </div>

      <div className="flex flex-col gap-3 p-4">
        <div className="flex h-2 overflow-hidden rounded-full bg-[#E8E8ED]">
          <div
            className={`h-full ${meta.bar} transition-[width] duration-700`}
            style={{ width: `${confidencePercent}%` }}
          />
        </div>

        {verdict.verdict_detail ? (
          <div className="flex items-center justify-between gap-2 rounded-xl border border-border-divider bg-bg-page/60 px-3 py-2 text-xs">
            <span className="font-medium text-text-primary">语义裁决</span>
            <span className={`rounded px-1.5 py-0.5 font-semibold ${meta.className}`}>
              {detailLabels[verdict.verdict_detail]}
            </span>
          </div>
        ) : null}

        <p className="rounded-xl bg-bg-page/70 p-3 text-xs leading-relaxed text-text-secondary">
          {verdict.short_reason}
          <span className="mt-1.5 block text-[11px] text-text-secondary/80">
            证据等级：{gradeLabels[verdict.evidence_grade]} · 支持 {supportingCount} 条 · 反对{" "}
            {opposingCount} 条 · 更新于 {verdict.last_updated}
          </span>
        </p>

        <p className="rounded-xl border border-dashed border-brand/25 bg-brand/5 px-3 py-2 text-xs leading-relaxed text-text-secondary">
          支持证据和反对 / 边界证据已经整理进下方 Flow，左右切换卡片，点击卡片可翻面查看完整研究信息。
        </p>

        {verdict.uncertainty.length ? (
          <div className="rounded-xl border border-border-divider bg-bg-page/40 p-3">
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-text-primary">
              <AlertTriangle size={13} className="text-evidence-boundary" />
              不确定性
            </p>
            <ul className="flex flex-col gap-1 text-xs text-text-secondary">
              {verdict.uncertainty.map((item, index) => (
                <li key={index} className="flex gap-1.5">
                  <HelpCircle size={12} className="mt-0.5 shrink-0 text-text-secondary/60" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {verdict.what_could_change_this_verdict?.length ? (
          <div className="rounded-xl border border-dashed border-evidence-boundary/30 bg-evidence-boundary/5 p-3">
            <p className="mb-1.5 text-xs font-semibold text-evidence-boundary">
              什么可能改变这个结论
            </p>
            <ul className="flex flex-col gap-1 text-xs text-text-secondary">
              {verdict.what_could_change_this_verdict.map((item, index) => (
                <li key={index} className="flex gap-1.5">
                  <RefreshCw size={12} className="mt-0.5 shrink-0 text-evidence-boundary/70" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}
