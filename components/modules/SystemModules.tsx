"use client";

import { useId } from "react";
import { AlertCircle, AlertTriangle, Ban, CheckCircle2, ExternalLink, Globe2, HeartHandshake, Info, MessageSquareText, Phone, ShieldCheck, ShieldAlert, Users } from "lucide-react";

interface ConfirmationCardProps {
  title?: string;
  message?: string;
  label?: string;
  onConfirm?: () => void;
  onCancel?: () => void;
}

export function ConfirmationCard({
  title = "需要确认",
  message = "请确认是否执行这项操作。",
  label = "确认操作",
  onConfirm,
  onCancel,
}: ConfirmationCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-brand bg-brand/5 p-4">
      <div className="flex items-center gap-2 font-semibold text-brand">
        <Info size={20} /> {title}
      </div>
      <p className="text-sm text-text-primary">{message}</p>
      <div className="mt-2 flex gap-3">
        <button type="button" onClick={onCancel} className="rounded-lg border border-border-divider bg-white px-4 py-2 text-sm font-medium text-text-secondary hover:bg-black/5">
          取消
        </button>
        <button type="button" onClick={onConfirm} className="flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90">
          <CheckCircle2 size={16} /> {label}
        </button>
      </div>
    </div>
  );
}

export function SafetyCard({
  title = "安全提示",
  message = "当前问题需要专业人员进一步评估。",
  severity = "high",
}: {
  title?: string;
  message?: string;
  severity?: "high" | "medium";
}) {
  const isHigh = severity === "high";
  return (
    <div className={`flex gap-3 rounded-xl border p-4 ${isHigh ? "border-risk-refused/20 bg-risk-refused/5 text-risk-refused" : "border-evidence-boundary/20 bg-evidence-boundary/5 text-evidence-boundary"}`}>
      <ShieldAlert size={24} className="shrink-0" />
      <div><h4 className="mb-1 font-semibold">{title}</h4><p className="text-sm opacity-90">{message}</p></div>
    </div>
  );
}

export function GeneralAnswerCard({
  title = "非医学通用回答",
  answer = "",
  classification_reason = "这个问题不属于医疗健康证据范围。",
  key_points = [],
  limitations = [],
  boundary_status = "limited",
  boundary_label = "伦理边界开启",
  search_results = [],
  search_status = "disabled",
  search_query = "",
}: {
  title?: string;
  answer?: string;
  classification_reason?: string;
  key_points?: string[];
  limitations?: string[];
  boundary_status?: "limited" | "blocked" | "unavailable";
  boundary_label?: string;
  search_results?: Array<{
    title: string;
    url: string;
    snippet?: string;
    source?: string;
    published_at?: string | null;
  }>;
  search_status?: "disabled" | "ok" | "empty" | "failed";
  search_query?: string;
}) {
  const blocked = boundary_status === "blocked";
  const titleId = useId();
  const publishedDate = (value?: string | null) => {
    if (!value) return null;
    const parsed = new Date(value);
    return Number.isNaN(parsed.valueOf()) ? value : parsed.toISOString().slice(0, 10);
  };

  return (
    <section
      aria-labelledby={titleId}
      className="overflow-hidden rounded-[26px] border border-[#8FB7F4]/35 bg-white text-[#1D2733] shadow-[0_18px_55px_rgba(55,91,142,0.10)]"
    >
      <div className={`h-1.5 ${blocked ? "bg-[#EF7065]" : "bg-[linear-gradient(90deg,#5DA9E9_0%,#68C8BC_58%,#F5C95E_100%)]"}`} />
      <div className="p-5 sm:p-7">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-start gap-3.5">
            <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${blocked ? "bg-[#FFF0EE] text-[#C64F46]" : "bg-[#EEF6FF] text-[#3479C6]"}`}>
              {blocked ? <Ban aria-hidden="true" size={22} /> : <MessageSquareText aria-hidden="true" size={22} />}
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold tracking-[0.16em] text-[#557086]">非医学问题</p>
              <h3 id={titleId} className="mt-1 text-xl font-semibold tracking-[-0.02em] text-[#1D2733] sm:text-2xl">{title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-[#6A7785]">{classification_reason}</p>
            </div>
          </div>
          <span className={`inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold ${blocked ? "bg-[#FFF0EE] text-[#B9453E]" : "bg-[#EFF9F6] text-[#287E75]"}`}>
            {blocked ? <Ban aria-hidden="true" size={14} /> : <ShieldCheck aria-hidden="true" size={14} />}
            {boundary_label}
          </span>
        </header>

        <div className="mt-6 border-l-2 border-[#A8C8F4] pl-4 sm:pl-5">
          <p className="whitespace-pre-wrap text-[15px] leading-7 text-[#263441] sm:text-base">{answer}</p>
          {key_points.length ? (
            <ul className="mt-4 space-y-2 text-sm leading-6 text-[#40515F]">
              {key_points.map((point) => (
                <li key={point} className="flex gap-2.5">
                  <span aria-hidden="true" className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#5DA9E9]" />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        {!blocked ? (
          <section className="mt-6 rounded-2xl border border-[#8FB7F4]/25 bg-[#F7FAFF] p-4 sm:p-5" aria-label="联网搜索来源">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="flex items-center gap-2 text-sm font-semibold text-[#315E8E]">
                <Globe2 aria-hidden="true" size={17} />联网搜索来源
              </p>
              {search_query ? <span className="max-w-full truncate text-xs text-[#71849A]">检索：{search_query}</span> : null}
            </div>
            {search_status === "ok" && search_results.length ? (
              <ol className="mt-4 grid gap-3 sm:grid-cols-2">
                {search_results.map((item, index) => (
                  <li key={`${item.url}-${index}`} className="rounded-xl bg-white p-3.5 shadow-sm ring-1 ring-black/[0.055]">
                    <a href={item.url} target="_blank" rel="noreferrer" className="group block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#3479C6]">
                      <span className="flex flex-wrap items-center gap-x-2 text-[11px] font-semibold text-[#5A7A9A]">
                        <span>[{index + 1}] {item.source || "网页来源"}</span>
                        {publishedDate(item.published_at) ? <time dateTime={item.published_at || undefined}>{publishedDate(item.published_at)}</time> : null}
                      </span>
                      <span className="mt-1 flex items-start gap-2 text-sm font-semibold leading-5 text-[#263F58] group-hover:text-[#3479C6]">
                        <span className="min-w-0 flex-1">{item.title}</span><ExternalLink aria-hidden="true" className="mt-0.5 shrink-0" size={14} />
                      </span>
                      {item.snippet ? <span className="mt-1.5 line-clamp-2 text-xs leading-5 text-[#6A7785]">{item.snippet}</span> : null}
                    </a>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-3 text-sm leading-6 text-[#6A7785]">
                {search_status === "failed"
                  ? "联网搜索暂时不可用，这次回答没有完成实时来源核验。"
                  : search_status === "empty"
                    ? "本次联网搜索没有返回可用来源。"
                    : "当前没有启用通用联网搜索。"}
              </p>
            )}
          </section>
        ) : null}

        <aside className={`mt-6 rounded-2xl border p-4 ${blocked ? "border-[#EF7065]/25 bg-[#FFF7F5]" : "border-[#F0C65A]/30 bg-[#FFF9E8]"}`}>
          <p className={`flex items-center gap-2 text-sm font-semibold ${blocked ? "text-[#A9423B]" : "text-[#725E22]"}`}>
            <ShieldAlert aria-hidden="true" size={17} />
            {blocked ? "禁止边界" : "这不是医疗证据结论"}
          </p>
          <p className={`mt-2 text-sm leading-6 ${blocked ? "text-[#78524E]" : "text-[#6E6547]"}`}>
            {blocked
              ? "系统可以解释风险、预防和合规背景，但不会提供可直接实施伤害、违法、欺诈或侵犯隐私的步骤。"
              : search_status === "ok"
                ? "回答由通用大模型结合上方联网结果生成，但没有进入医疗数据库、医学文献核验或中医视角 Flow；不要把它用于诊断、用药或紧急健康决策。"
                : "回答由通用大模型生成，但本次没有完成联网来源核验，也没有进入医疗 Evidence Flow。"}
          </p>
          {limitations.length ? (
            <ul className={`mt-2 list-disc space-y-1 pl-5 text-sm leading-6 ${blocked ? "text-[#78524E]" : "text-[#6E6547]"}`}>
              {limitations.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

interface CrisisContact {
  label: string;
  number: string;
}

export function CrisisSupportCard({
  title = "谢谢你把这些说出来，你不用一个人扛",
  message = "我很在意你现在是否安全。先联系一个能够到你身边的人。",
  crisis_level = "concern",
  check_in_question = "你现在安全吗？",
  immediate_steps = [],
  supportive_note = "你现在不需要解决整个人生，只需要先把接下来的十分钟安全地过完。",
  reply_options = ["现在安全", "有危险"],
  reach_out_message = "我现在状态很差，一个人有点撑不住。你能现在给我打个电话，或者来陪我待一会儿吗？",
  avoid_actions = [],
  emergency_contacts = [],
}: {
  title?: string;
  message?: string;
  crisis_level?: "concern" | "imminent";
  check_in_question?: string;
  immediate_steps?: string[];
  supportive_note?: string;
  reply_options?: string[];
  reach_out_message?: string;
  avoid_actions?: string[];
  emergency_contacts?: CrisisContact[];
}) {
  const imminent = crisis_level === "imminent";
  const titleId = useId();

  return (
    <section
      aria-labelledby={titleId}
      className="overflow-hidden rounded-[28px] border border-[#70C1B3]/35 bg-[#F4FCFA] text-[#173B3A] shadow-[0_22px_70px_rgba(27,85,81,0.10)]"
    >
      <div className="h-2 bg-[linear-gradient(90deg,#58C7B4_0%,#70A7E8_48%,#FFD45C_100%)]" />
      <div className="grid gap-6 p-6 sm:p-8 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div>
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-[#287E75] shadow-sm ring-1 ring-[#70C1B3]/25">
            <HeartHandshake aria-hidden="true" size={25} />
          </div>
          <p className="mb-2 text-xs font-semibold tracking-[0.16em] text-[#287E75]">
            先照顾此刻的安全
          </p>
          <h3 id={titleId} className="text-balance text-2xl font-semibold leading-tight text-[#173B3A] sm:text-[28px]">
            {title}
          </h3>
          <p className="mt-3 max-w-2xl text-[15px] leading-7 text-[#496362]">{message}</p>

          <div className="mt-6 rounded-2xl border border-[#70A7E8]/30 bg-white p-4 shadow-sm">
            <p className="flex items-start gap-3 font-semibold leading-6 text-[#244E74]">
              <Users aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
              {check_in_question}
            </p>
            {reply_options.length ? (
              <div className="mt-3 flex flex-wrap gap-2" aria-label="可以直接回复">
                {reply_options.map((option, index) => (
                  <span
                    key={option}
                    className={`rounded-full px-3 py-1.5 text-xs font-semibold ${index === 0 ? "bg-[#EAF7F3] text-[#287E75]" : "bg-[#FFF0EE] text-[#B84D45]"}`}
                  >
                    {option}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          <div className="mt-4 rounded-2xl bg-[#EAF3FF] p-4 text-[#244E74] ring-1 ring-[#70A7E8]/25">
            <p className="text-xs font-semibold tracking-[0.08em]">不知道怎么开口，可以把这句话发出去</p>
            <blockquote className="mt-2 select-text border-l-2 border-[#70A7E8] pl-3 text-sm leading-6">
              “{reach_out_message}”
            </blockquote>
          </div>

          <ol className="mt-6 space-y-3">
            {immediate_steps.map((step, index) => (
              <li key={step} className="flex gap-3 text-sm leading-6 text-[#365553]">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#DDF4EF] text-xs font-bold text-[#287E75]">
                  {index + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>

        <aside className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-black/[0.055]">
          <p className="text-sm font-semibold text-[#173B3A]">
            {imminent ? "现在就联系" : "需要时可以联系"}
          </p>
          <div className="mt-4 space-y-2.5">
            {emergency_contacts.map((contact, index) => (
              <a
                key={`${contact.label}-${contact.number}`}
                href={`tel:${contact.number}`}
                className={`flex min-h-12 items-center justify-between rounded-2xl px-4 py-3 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#287E75] ${
                  imminent && index === 0
                    ? "bg-[#E8665B] text-white hover:bg-[#D95B51]"
                    : "bg-[#EEF8F6] text-[#245E59] hover:bg-[#E1F3EF]"
                }`}
              >
                <span>{contact.label}</span>
                <span className="flex items-center gap-2 font-mono text-base">
                  <Phone aria-hidden="true" size={16} /> {contact.number}
                </span>
              </a>
            ))}
          </div>
          <p className="mt-5 rounded-2xl bg-[#FFF7D9] p-4 text-sm leading-6 text-[#66551D]">
            {supportive_note}
          </p>
          {avoid_actions.length ? (
            <details className="mt-4 text-sm text-[#607170]">
              <summary className="cursor-pointer font-medium text-[#496362]">此刻先避免什么</summary>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 leading-6">
                {avoid_actions.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </details>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

export function ExtremeCrisisCareCard({
  title = "我认真看到了这句话。现在先让人来到你身边",
  message = "你不需要现在解释所有事情。先停下可能伤害自己的动作，离开危险位置，让现实中的人马上陪着你。",
  check_in_question = "你只要先回答一句：已经有危险，还是现在暂时安全？",
  reply_options = ["现在安全", "有危险"],
  reach_out_message = "我现在可能会伤害自己。请马上给我打电话或来陪我，并帮我联系急救或报警，不要让我一个人待着。",
  immediate_steps = [],
  supportive_note = "你现在不用解决整个人生。先和一个真实的人把接下来的十分钟安全地过完。",
  emergency_contacts = [],
}: {
  title?: string;
  message?: string;
  check_in_question?: string;
  reply_options?: string[];
  reach_out_message?: string;
  immediate_steps?: string[];
  supportive_note?: string;
  emergency_contacts?: CrisisContact[];
  avoid_actions?: string[];
  crisis_level?: "imminent";
}) {
  const titleId = useId();

  return (
    <section
      aria-labelledby={titleId}
      className="overflow-hidden rounded-[30px] border border-[#F06A5F]/30 bg-[#FFF9F7] text-[#2D2928] shadow-[0_24px_80px_rgba(111,57,51,0.14)]"
    >
      <div className="h-2 bg-[linear-gradient(90deg,#F06A5F_0%,#F4C95D_42%,#64C4B2_100%)]" />
      <div className="p-5 sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-[#C84F46] shadow-sm ring-1 ring-[#F06A5F]/20">
                <HeartHandshake aria-hidden="true" size={26} />
              </div>
              <div>
                <p className="text-xs font-bold tracking-[0.14em] text-[#B54A43]">现在先不讨论证据</p>
                <p className="mt-1 text-sm text-[#78625F]">先确保你身边有人、危险物品已经移开</p>
              </div>
            </div>
            <h3 id={titleId} className="mt-5 text-balance text-2xl font-semibold leading-tight tracking-[-0.025em] text-[#352827] sm:text-[30px]">
              {title}
            </h3>
            <p className="mt-3 text-[15px] leading-7 text-[#695653]">{message}</p>
          </div>

          <div className="shrink-0 rounded-2xl border border-[#F06A5F]/20 bg-white px-4 py-3 text-sm font-semibold text-[#A6443E] shadow-sm">
            <span className="inline-flex items-center gap-2"><ShieldAlert aria-hidden="true" size={18} />需要立即连接现实支持</span>
          </div>
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_310px]">
          <div className="space-y-4">
            <div className="rounded-3xl border border-[#6FA8E8]/30 bg-white p-5 shadow-sm">
              <p className="flex gap-3 text-base font-semibold leading-7 text-[#264F78]">
                <Users aria-hidden="true" className="mt-1 shrink-0" size={20} />
                <span>{check_in_question}</span>
              </p>
              <div className="mt-4 flex flex-wrap gap-2" aria-label="可以直接回复">
                {reply_options.map((option, index) => (
                  <span key={option} className={`rounded-full px-4 py-2 text-sm font-semibold ${index === 0 ? "bg-[#E8F6F1] text-[#287E75]" : "bg-[#FFE9E6] text-[#B4423A]"}`}>
                    {option}
                  </span>
                ))}
              </div>
            </div>

            <div className="rounded-3xl bg-[#EAF3FF] p-5 text-[#244E74] ring-1 ring-[#6FA8E8]/25">
              <p className="text-xs font-bold tracking-[0.08em]">不方便解释时，直接把这句话发给身边的人</p>
              <blockquote className="mt-3 select-text border-l-2 border-[#6FA8E8] pl-4 text-[15px] leading-7">
                “{reach_out_message}”
              </blockquote>
            </div>

            <ol className="space-y-3 rounded-3xl bg-white p-5 ring-1 ring-black/[0.06]">
              {immediate_steps.slice(0, 4).map((step, index) => (
                <li key={step} className="flex gap-3 text-sm leading-6 text-[#594E4C]">
                  <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${index === 2 ? "bg-[#FFE5E1] text-[#B4423A]" : "bg-[#E8F6F1] text-[#287E75]"}`}>
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>

          <aside className="rounded-3xl bg-[#253B4D] p-5 text-white shadow-[0_18px_50px_rgba(37,59,77,0.18)]">
            <p className="text-sm font-semibold">现在可以拨打</p>
            <p className="mt-1 text-xs leading-5 text-white/65">如果你无法自己拨号，把屏幕交给身边的人。</p>
            <div className="mt-5 space-y-3">
              {emergency_contacts.map((contact, index) => (
                <a
                  key={`${contact.label}-${contact.number}`}
                  href={`tel:${contact.number}`}
                  className={`flex min-h-14 items-center justify-between rounded-2xl px-4 py-3 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${index < 2 ? "bg-[#F06A5F] text-white hover:bg-[#DF5C52]" : "bg-white/10 text-white hover:bg-white/15"}`}
                >
                  <span>{contact.label}</span>
                  <span className="flex items-center gap-2 font-mono text-lg"><Phone aria-hidden="true" size={17} />{contact.number}</span>
                </a>
              ))}
            </div>
            <p className="mt-5 rounded-2xl bg-[#F4C95D] p-4 text-sm font-medium leading-6 text-[#514313]">{supportive_note}</p>
          </aside>
        </div>
      </div>
    </section>
  );
}

export function ErrorRecovery({
  message = "请求失败，请稍后重试。",
  retryable = false,
  onRetry,
}: {
  message?: string;
  retryable?: boolean;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-xl border border-risk-refused/20 bg-risk-refused/5 p-4 text-risk-refused">
      <div className="flex items-center gap-2 font-semibold"><AlertCircle size={20} />发生错误</div>
      <p className="text-sm">{message}</p>
      {retryable && onRetry ? <button type="button" onClick={onRetry} className="rounded-lg bg-risk-refused px-4 py-2 text-sm font-medium text-white hover:bg-risk-refused/90">重试</button> : null}
    </div>
  );
}

export function UnsupportedModule({ type = "unknown" }: { type?: string }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border-divider bg-text-secondary/5 p-4 text-text-secondary">
      <div className="flex items-center gap-2 font-semibold"><AlertTriangle size={20} />暂不支持的模块</div>
      <p className="text-sm">系统返回了当前版本无法渲染的模块：<span className="rounded bg-bg-page px-1 font-mono">{type}</span>。其他内容仍可继续使用。</p>
    </div>
  );
}

export function LoadingModule({ message = "正在处理..." }: { message?: string }) {
  return <div className="flex items-center gap-3 p-4 text-text-secondary"><div className="h-5 w-5 animate-spin rounded-full border-2 border-text-secondary/30 border-t-text-secondary" /><span className="text-sm">{message}</span></div>;
}

interface ClarificationOption { label: string; value: string }

export function ClarificationCard({
  question = "请补充更多信息",
  options = [],
  onSelect,
}: {
  question?: string;
  options?: ClarificationOption[];
  onSelect?: (value: string) => void;
}) {
  return (
    <div className="rounded-xl border border-border-divider bg-white p-4 shadow-sm">
      <h4 className="mb-3 font-medium text-text-primary">{question}</h4>
      <div className="flex flex-col gap-2">
        {options.map((option) => <button type="button" key={option.value} onClick={() => onSelect?.(option.value)} className="rounded-lg border border-border-divider px-4 py-3 text-left text-sm text-text-primary hover:bg-bg-page">{option.label}</button>)}
      </div>
    </div>
  );
}
