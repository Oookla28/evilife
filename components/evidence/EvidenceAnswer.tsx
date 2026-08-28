"use client";

import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  BookOpen,
  ChevronDown,
  Database,
  ExternalLink,
  FileText,
  Globe2,
  ListChecks,
  Route as RouteIcon,
  ShieldAlert,
  X,
} from "lucide-react";
import type { EvidenceCitation } from "@/lib/api/adapters";
import type { EvidenceNote, HealthClaim, TraceStep } from "@/lib/api/types";
import { MedicalEvidenceCardFlow } from "@/components/evidence/MedicalEvidenceCardFlow";
import { buildMedicalFlowCards, type MedicalFlowCard } from "@/lib/evidence/build-medical-flow-cards";
import { VerdictCard, type VerdictProps } from "@/components/evidence/VerdictCard";

interface DebugMetadata {
  requestId?: string;
  runId?: string;
  timingMs?: Record<string, number>;
}

interface EvidenceMix {
  reliable_weight?: number;
  general_weight?: number;
  target_reliable_weight?: number;
  policy_reason?: string;
  live_search_status?: "disabled" | "ok" | "empty" | "failed";
  trusted_source_count?: number;
}

interface TCMPerspective {
  title: string;
  summary: string;
  topic_link?: string;
  perspective?: string[];
  questions: string[];
  safe_ideas: string[];
  limitations?: string[];
  avoid: string;
  evidence_note: string;
  ai_summary?: string;
  source?: "ai" | "deterministic_fallback";
  sources: Array<{ source_id: string; title: string; organization: string; year?: number | null; url: string; role: string }>;
}

export interface EvidenceAnswerProps {
  conclusion?: string;
  gate_status?: "normal" | "degraded" | "refused";
  evidence_strength?: "high" | "medium" | "low" | "insufficient";
  explanation?: string;
  target_population?: string[];
  non_target_population?: string[];
  general_advice?: string[];
  limitations?: string[];
  citations?: EvidenceCitation[];
  status?: string;
  source?: string;
  model?: string;
  packet_id?: string;
  evidence_mix?: EvidenceMix;
  verdict?: VerdictProps;
  claims?: HealthClaim[];
  trace_steps?: TraceStep[];
  dynamic_notes?: EvidenceNote[];
  tcm_perspective?: TCMPerspective;
  debug?: DebugMetadata;
}

const strengthClasses = {
  high: "bg-evidence-support text-white",
  medium: "bg-brand text-white",
  low: "bg-evidence-boundary text-white",
  insufficient: "bg-risk-refused text-white",
};

const strengthLabels = {
  high: "高质量证据",
  medium: "中等质量证据",
  low: "低质量证据",
  insufficient: "证据不足",
};

const gateStyles = {
  normal: "border-evidence-support/25 bg-evidence-support/5 text-evidence-support",
  degraded: "border-evidence-boundary/30 bg-evidence-boundary/5 text-evidence-boundary",
  refused: "border-risk-refused/25 bg-risk-refused/5 text-risk-refused",
};

const claimTypeLabels: Record<string, string> = {
  effectiveness: "效果",
  causal: "因果",
  risk_factor: "风险因素",
  metabolic: "代谢",
  safety_or_body_composition: "安全/体成分",
  longevity: "长寿",
  comparison: "比较",
  population_claim: "人群主张",
  other: "其他",
};

function ClaimsPanel({ claims }: { claims: HealthClaim[] }) {
  return (
    <section
      aria-label="拆解主张"
      className="rounded-xl border border-border-divider bg-bg-page/40 p-3"
    >
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-text-primary">
        <ListChecks size={14} className="text-brand" />
        这句话拆解成 {claims.length} 条待核验主张
      </p>
      <ul className="flex flex-col gap-1.5">
        {claims.map((claim) => (
          <li key={claim.claim_id} className="flex items-start gap-2 text-xs">
            <span className="mt-0.5 shrink-0 rounded bg-bg-page px-1 py-0.5 font-mono text-[10px] text-brand">
              {claim.claim_id}
            </span>
            <span className="min-w-0 flex-1 leading-relaxed text-text-primary">
              {claim.claim}
            </span>
            <span className="shrink-0 rounded bg-white/60 px-1 py-0.5 text-[10px] text-text-secondary">
              {claimTypeLabels[claim.type] ?? claim.type}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

const noteDirectionMeta: Record<
  EvidenceNote["direction"],
  { label: string; className: string }
> = {
  support: { label: "支持", className: "bg-evidence-support/10 text-evidence-support border-evidence-support/20" },
  against: { label: "反对", className: "bg-evidence-boundary/10 text-evidence-boundary border-evidence-boundary/20" },
  mixed: { label: "混合", className: "bg-brand/10 text-brand border-brand/20" },
  context: { label: "语境", className: "bg-bg-page/60 text-text-secondary border-border-divider" },
};

function NoteSection({ title, items, tone }: { title: string; items: string[]; tone: "support" | "against" }) {
  if (!items.length) return null;
  const color = tone === "support" ? "text-evidence-support" : "text-evidence-boundary";
  return (
    <div className="mt-2">
      <p className={`text-[11px] font-semibold ${color}`}>{title}</p>
      <ul className="mt-0.5 flex flex-col gap-0.5 text-[11px] leading-relaxed text-text-secondary">
        {items.map((item, index) => (
          <li key={index}>· {item}</li>
        ))}
      </ul>
    </div>
  );
}

function DynamicNotesPanel({ notes }: { notes: EvidenceNote[] }) {
  const [open, setOpen] = useState(false);
  const supportCount = notes.filter((n) => n.direction === "support").length;
  const opposeCount = notes.filter((n) => n.direction === "against").length;
  const mixedCount = notes.filter((n) => n.direction === "mixed").length;
  const visible = open ? notes : notes.slice(0, 3);

  return (
    <section
      aria-label="动态证据"
      className="rounded-xl border border-border-divider bg-bg-page/30 p-3"
    >
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
          <Database size={14} className="text-brand" />
          动态检索证据 · {notes.length} 篇
        </span>
        <span className="flex items-center gap-2 text-[11px] text-text-secondary">
          <span className="text-evidence-support">支持 {supportCount}</span>
          <span className="text-evidence-boundary">反对 {opposeCount}</span>
          {mixedCount ? <span className="text-brand">混合 {mixedCount}</span> : null}
          <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </span>
      </button>

      {open ? (
        <div className="mt-3 flex flex-col gap-2">
          {visible.map((note) => {
            const meta = noteDirectionMeta[note.direction] ?? noteDirectionMeta.context;
            return (
              <article key={note.evidence_id} className="rounded-xl border border-border-divider bg-white p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-medium leading-snug text-text-primary">
                    {note.title}
                    <span className="ml-1.5 text-text-secondary/70">
                      {[note.year, note.study_type].filter(Boolean).join(" · ")}
                    </span>
                  </p>
                  <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${meta.className}`}>
                    {meta.label}
                  </span>
                </div>

                {note.finding ? (
                  <p className="mt-1.5 text-xs leading-relaxed text-text-secondary">
                    {note.finding}
                  </p>
                ) : null}

                <NoteSection title="支持点" items={note.supports} tone="support" />
                <NoteSection title="不支持/边界" items={note.does_not_support} tone="against" />
                <NoteSection title="局限" items={note.limitations} tone="against" />

                {note.sample_size ? (
                  <p className="mt-1.5 text-[11px] text-text-secondary/80">样本量 N = {note.sample_size}</p>
                ) : null}
                {note.url ? (
                  <a
                    href={note.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 inline-flex items-center gap-1 text-[11px] text-brand hover:opacity-80"
                  >
                    查看原始来源 <ExternalLink size={10} />
                  </a>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}

function TracePanel({ steps }: { steps: TraceStep[] }) {
  const [open, setOpen] = useState(false);
  if (!steps.length) return null;
  return (
    <div className="border-t border-border-divider pt-4">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between text-xs font-medium text-text-primary"
      >
        <span className="flex items-center gap-1.5">
          <RouteIcon size={14} className="text-text-secondary" />
          证据链 · {steps.length} 步
        </span>
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <ol className="mt-3 flex flex-col gap-2">
          {steps.map((step, index) => (
            <li key={`${step.step}-${index}`} className="flex items-start gap-2 text-xs">
              <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-bg-page font-mono text-[10px] text-text-secondary">
                {index + 1}
              </span>
              <div className="min-w-0">
                <p className="font-medium text-text-primary">
                  {step.step}
                  {step.status === "failed" ? (
                    <span className="ml-1.5 rounded bg-risk-refused/10 px-1 py-0.5 text-[10px] text-risk-refused">
                      拦截
                    </span>
                  ) : null}
                </p>
                {step.output_summary ? (
                  <p className="mt-0.5 leading-relaxed text-text-secondary">
                    {step.output_summary}
                  </p>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

function CitationDrawer({
  citation,
  onClose,
}: {
  citation: EvidenceCitation;
  onClose: () => void;
}) {
  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end md:items-stretch md:justify-end">
      <button
        type="button"
        aria-label="关闭来源详情"
        className="absolute inset-0 bg-black/25 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <aside
        aria-label="来源详情"
        className="relative z-10 w-full max-h-[82dvh] overflow-y-auto rounded-t-3xl bg-white p-5 shadow-2xl md:h-full md:max-h-none md:max-w-md md:rounded-none md:border-l md:border-border-divider md:p-7"
      >
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="mb-2 font-mono text-xs text-brand">[{citation.id}]</p>
            <h3 className="text-lg font-semibold leading-snug text-text-primary">
              {citation.title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="rounded-full p-2 text-text-secondary transition-colors hover:bg-black/5"
          >
            <X size={18} />
          </button>
        </div>

        <dl className="space-y-4 text-sm">
          {citation.organization ? (
            <div>
              <dt className="text-text-secondary">机构</dt>
              <dd className="mt-1 text-text-primary">{citation.organization}</dd>
            </div>
          ) : null}
          {citation.year ? (
            <div>
              <dt className="text-text-secondary">年份</dt>
              <dd className="mt-1 text-text-primary">{citation.year}</dd>
            </div>
          ) : null}
          {citation.sourceType ? (
            <div>
              <dt className="text-text-secondary">来源类型</dt>
              <dd className="mt-1 text-text-primary">{citation.sourceType}</dd>
            </div>
          ) : null}
          {citation.sourceId ? (
            <div>
              <dt className="text-text-secondary">来源编号</dt>
              <dd className="mt-1 break-all font-mono text-xs text-text-primary">
                {citation.sourceId}
              </dd>
            </div>
          ) : null}
        </dl>

        {citation.url ? (
          <a
            href={citation.url}
            target="_blank"
            rel="noreferrer"
            className="mt-7 inline-flex items-center gap-2 rounded-xl bg-text-primary px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            查看原始来源 <ExternalLink size={15} />
          </a>
        ) : (
          <p className="mt-7 rounded-xl bg-bg-page p-3 text-xs text-text-secondary">
            当前来源没有可访问链接。
          </p>
        )}
      </aside>
    </div>,
    document.body
  );
}

export function EvidenceAnswer({
  conclusion,
  gate_status = "normal",
  evidence_strength,
  explanation,
  target_population,
  non_target_population,
  general_advice,
  limitations,
  citations = [],
  source,
  model,
  packet_id,
  evidence_mix,
  verdict,
  claims,
  trace_steps,
  dynamic_notes,
  tcm_perspective,
  debug,
}: EvidenceAnswerProps) {
  const [selectedCitation, setSelectedCitation] = useState<EvidenceCitation | null>(null);
  const isVerifiedPacket = Boolean(packet_id) || source === "fast_path";
  const isHybridEvidence = source?.startsWith("hybrid_");
  const isAiGenerated = source?.startsWith("ai_") || Boolean(model);
  const flowCards = useMemo(
    () =>
      {
        const cards = buildMedicalFlowCards({
          conclusion,
          explanation,
          supportingEvidence: verdict?.supporting_evidence,
          opposingEvidence: verdict?.opposing_evidence,
          targetPopulation: target_population,
        nonTargetPopulation: non_target_population,
        generalAdvice: general_advice,
        limitations,
        });
        if (tcm_perspective) {
          const perspective = tcm_perspective.perspective ?? [];
          const topicLink = tcm_perspective.topic_link ?? tcm_perspective.summary;
          const aiSummary = tcm_perspective.ai_summary ?? tcm_perspective.summary;
          const tcmCard: MedicalFlowCard = {
            id: "tcm-perspective",
            title: "中医视角",
            tag: tcm_perspective.source === "ai" ? "AI 辅助分析 · 非诊断" : "辅助观察 · 非诊断",
            preview: topicLink,
            body: [topicLink, ...perspective, aiSummary].filter(Boolean).join("\n"),
            tone: "population",
            icon: "tcm",
            details: [
              { label: "与当前问题的关系", value: topicLink },
              ...(perspective.length ? [{ label: "中医辅助分析", value: perspective.join("；") }] : []),
              { label: "辨证前还要问", value: tcm_perspective.questions.join("；") },
              { label: "低风险生活思路", value: tcm_perspective.safe_ideas.join("；") },
              { label: "不能据此操作", value: tcm_perspective.avoid },
              ...(tcm_perspective.limitations?.length ? [{ label: "分析局限", value: tcm_perspective.limitations.join("；") }] : []),
              { label: "证据策略", value: tcm_perspective.evidence_note },
              { label: "AI 综合总结", value: aiSummary },
              ...tcm_perspective.sources.map((item, index) => ({
                label: `参考文献 ${index + 1}`,
                value: `${item.title}\n${item.organization}${item.year ? ` · ${item.year}` : ""} · ${item.role}${item.url ? `\n${item.url}` : ""}`,
              })),
            ],
          };
          cards.push(tcmCard);
        }
        return cards;
      },
    [
      conclusion,
      explanation,
      general_advice,
      limitations,
      non_target_population,
      target_population,
      tcm_perspective,
      verdict,
    ]
  );
  const flowKey = flowCards.map((card) => `${card.id}:${card.body}`).join("|");

  const footerText = isHybridEvidence
    ? "结论由可追溯医学证据约束，全文语境仅用于解释，仍不能替代专业医疗诊断。"
    : isVerifiedPacket
    ? "结论来自预编译并校验过的证据包，但仍不能替代专业医疗诊断。"
    : isAiGenerated
      ? "这是 AI 生成的一般健康信息，未经过来源库核验，不能替代专业医疗建议。"
      : "当前信息缺少经过核验的来源，请勿据此自行诊断、停药或调整治疗。";

  return (
    <article className="overflow-hidden rounded-2xl border border-border-divider bg-white shadow-sm">
      <div className="border-b border-border-divider bg-bg-page/50 p-5">
        <div className="mb-3 flex flex-col items-start justify-between gap-3 sm:flex-row">
          <h2 className="pr-2 text-lg font-bold leading-snug text-text-primary">
            {conclusion || "正在生成结论..."}
          </h2>
          {evidence_strength ? (
            <span
              className={`whitespace-nowrap rounded px-2 py-1 text-xs font-semibold ${strengthClasses[evidence_strength]}`}
            >
              {strengthLabels[evidence_strength]}
            </span>
          ) : null}
        </div>
        {explanation ? (
          <p className="whitespace-pre-line text-sm leading-relaxed text-text-secondary">
            {explanation}
          </p>
        ) : null}
      </div>

      <div className="flex flex-col gap-5 p-5">
        {gate_status !== "normal" ? (
          <div className={`flex gap-3 rounded-xl border p-3 text-sm ${gateStyles[gate_status]}`}>
            <ShieldAlert size={18} className="mt-0.5 shrink-0" />
            <p>
              {gate_status === "refused"
                ? "这个问题涉及不适合直接回答的医疗决策，系统已限制输出。"
                : "该回答没有经过完整证据核验，请把它视为一般性信息。"}
            </p>
          </div>
        ) : null}

        {verdict ? (
          <VerdictCard verdict={verdict} />
        ) : null}

        {claims?.length ? <ClaimsPanel claims={claims} /> : null}

        {dynamic_notes?.length ? <DynamicNotesPanel notes={dynamic_notes} /> : null}

        {evidence_mix ? (
          <section
            aria-label="回答数据来源配比"
            className="border-y border-border-divider py-3"
          >
            <div className="mb-2 flex items-center justify-between gap-3 text-xs">
              <span className="flex items-center gap-1.5 font-medium text-text-primary">
                <Database size={14} className="text-brand" />
                可追溯证据 {Math.round((evidence_mix.reliable_weight ?? 0) * 100)}%
              </span>
              <span className="flex items-center gap-1.5 text-text-secondary">
                <Globe2 size={14} />
                全文语境 {Math.round((evidence_mix.general_weight ?? 1) * 100)}%
              </span>
            </div>
            <div className="flex h-1.5 overflow-hidden rounded-full bg-[#E8E8ED]">
              <div
                className="h-full bg-brand transition-[width] duration-500"
                style={{ width: `${(evidence_mix.reliable_weight ?? 0) * 100}%` }}
              />
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-text-secondary">
              {evidence_mix.policy_reason}
              {evidence_mix.live_search_status === "ok"
                ? ` 已联网核对，共使用 ${evidence_mix.trusted_source_count ?? 0} 条可追溯来源。`
                : " 联网证据不足时，系统会自动降低结论强度。"}
            </p>
          </section>
        ) : null}

        <MedicalEvidenceCardFlow key={flowKey} cards={flowCards} />

        {citations.length ? (
          <section className="border-t border-border-divider pt-4">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-text-primary">
              <FileText size={16} className="text-text-secondary" /> 来源与引用
            </h3>
            <div className="flex flex-col gap-2">
              {citations.map((citation) => (
                <button
                  type="button"
                  key={`${citation.id}-${citation.sourceId ?? citation.title}`}
                  onClick={() => setSelectedCitation(citation)}
                  className="group flex items-start gap-3 rounded-xl border border-transparent p-2 text-left transition-colors hover:border-border-divider hover:bg-bg-page"
                >
                  <span className="rounded bg-bg-page px-1.5 py-0.5 font-mono text-xs text-brand">
                    [{citation.id}]
                  </span>
                  <span className="min-w-0 text-xs leading-relaxed text-text-secondary group-hover:text-text-primary">
                    {citation.title}
                    {[citation.organization, citation.year].filter(Boolean).length ? (
                      <span className="ml-1 text-text-secondary/70">
                        · {[citation.organization, citation.year].filter(Boolean).join(" · ")}
                      </span>
                    ) : null}
                  </span>
                </button>
              ))}
            </div>
          </section>
        ) : null}

        {process.env.NODE_ENV === "development" && (source || model || debug) ? (
          <details className="border-t border-border-divider pt-4 text-xs text-text-secondary">
            <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-text-primary">
              <BookOpen size={14} /> 调试信息 <ChevronDown size={14} />
            </summary>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-xl bg-bg-page p-3 font-mono">
              {source ? <><dt>route</dt><dd>{source}</dd></> : null}
              {model ? <><dt>model</dt><dd>{model}</dd></> : null}
              {debug?.requestId ? <><dt>request</dt><dd className="break-all">{debug.requestId}</dd></> : null}
              {debug?.runId ? <><dt>run</dt><dd className="break-all">{debug.runId}</dd></> : null}
              {debug?.timingMs ? <><dt>timing</dt><dd>{JSON.stringify(debug.timingMs)}</dd></> : null}
            </dl>
          </details>
        ) : null}

        {trace_steps?.length ? <TracePanel steps={trace_steps} /> : null}
      </div>

      <footer className={`border-t p-3 text-center text-xs ${gateStyles[gate_status]}`}>
        {footerText}
      </footer>

      {selectedCitation ? (
        <CitationDrawer citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
      ) : null}
    </article>
  );
}
