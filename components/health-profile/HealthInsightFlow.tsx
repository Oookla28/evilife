"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import QRCode from "qrcode";
import { Bot, Cable, FileInput, HeartPulse, LoaderCircle, ShieldCheck, Smartphone, Upload } from "lucide-react";
import { MedicalEvidenceCardFlow } from "@/components/evidence/MedicalEvidenceCardFlow";
import { ComprehensiveHealthCard } from "./ComprehensiveHealthCard";
import { analyzeHealthProfile, createHealthPairing, deleteObservation, getAppleHealthImport, getHealthConnectors, getHealthPairing, startAppleHealthImport, type CompletedAppleHealthImport, type HealthConnector, type ObservationRecord, type PairingSession, type ProfileAnalysisCard } from "@/lib/api/health-profile";
import type { MedicalFlowCard } from "@/lib/evidence/build-medical-flow-cards";
import type { MedicalCardIcon } from "@/lib/evidence/build-medical-flow-cards";

const statusLabel = {
  requires_native_bridge: "需要手机端授权 / 原生桥接",
  requires_credentials: "需要开发者配置 / 用户授权",
  available: "导入接口已就绪",
} as const;
const observationLabel: Record<string, string> = { water_ml: "饮水", steps: "步数", sleep_minutes: "睡眠", weight_kg: "体重", waist_cm: "腰围", resting_heart_rate: "静息心率", mood_score: "心情", note: "备注" };
const observationIcon: Record<string, MedicalCardIcon> = { water_ml: "water", steps: "activity", sleep_minutes: "sleep", weight_kg: "body", waist_cm: "body", resting_heart_rate: "heart", mood_score: "mood", note: "note" };

function connectorIcon(id: HealthConnector["id"]) {
  if (id === "generic_import") return FileInput;
  if (id === "apple_healthkit") return HeartPulse;
  return Smartphone;
}

function observationCards(records: ObservationRecord[]): MedicalFlowCard[] {
  return records.filter((record) => record.source !== "device").slice(0, 3).map((record) => {
    const label = observationLabel[record.kind] ?? record.kind;
    const value = record.kind === "note" ? record.note ?? "" : String(record.value ?? "未记录");
    return {
      id: `observation:${record.id}`,
      title: `${label}记录`,
      tag: record.source === "device" ? "设备同步记录" : "本人记录",
      preview: `${new Date(record.observed_at).toLocaleString("zh-CN")} · ${value}`,
      body: value,
      tone: "summary",
      icon: observationIcon[record.kind] ?? "note",
      details: [
        { label: "记录值", value },
        { label: "记录时间", value: new Date(record.observed_at).toLocaleString("zh-CN") },
        { label: "数据来源", value: record.connector_id ?? record.source },
      ],
    };
  });
}

function appleImportCard(result: CompletedAppleHealthImport): MedicalFlowCard {
  const { summary } = result;
  const labels = Object.entries(summary.counts)
    .filter(([, count]) => Boolean(count))
    .map(([kind, count]) => `${observationLabel[kind] ?? kind} ${count} 天`);
  return {
    id: `apple-import:${result.jobId}`,
    title: "Apple 健康数据已导入",
    tag: "批量导入摘要",
    preview: `一次完成 ${summary.accepted} 条每日汇总；原始数据不会逐条打印。`,
    body: labels.join("、"),
    tone: "summary",
    icon: "connect",
    details: [
      { label: "导入结果", value: `新增 ${summary.accepted} 条，跳过重复 ${summary.skipped} 条` },
      { label: "日期范围", value: summary.date_from && summary.date_to ? `${summary.date_from} 至 ${summary.date_to}` : "没有可导入日期" },
      { label: "每日汇总", value: labels.join("、") || "没有发现当前支持的健康类型" },
      { label: "处理方式", value: `流式检查 ${summary.processed_records.toLocaleString()} 条原始记录，仅打印本摘要卡一次。` },
    ],
  };
}

function latestValue(records: ObservationRecord[], kind: ObservationRecord["kind"], unit: string) {
  const record = records.find((item) => item.kind === kind && item.value != null);
  return record ? `${record.value?.toLocaleString()} ${unit}` : "未记录";
}

function metricTrend(records: ObservationRecord[], kind: ObservationRecord["kind"], label: string, unit: string, chart: "bar" | "line", color: string): MedicalFlowCard["trend"] {
  const points = records
    .filter((record) => record.kind === kind && record.value != null)
    .map((record) => ({
      date: record.observed_at,
      value: record.value as number,
      source: record.connector_id === "apple_healthkit" ? "Apple 健康导出" : record.source === "self_report" ? "本人记录" : record.connector_id ?? "设备记录",
    }))
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  return points.length ? { label, unit, chart, color, points } : undefined;
}

function functionalCards(records: ObservationRecord[]): MedicalFlowCard[] {
  const today = new Date().toLocaleDateString("zh-CN");
  const todayRecords = records.filter((item) => new Date(item.observed_at).toLocaleDateString("zh-CN") === today);
  const kinds = new Set(todayRecords.map((item) => item.kind));
  const deviceCount = records.filter((item) => item.source === "device").length;
  return [
    {
      id: "profile-today",
      title: "今日记录",
      tag: "健康档案",
      preview: todayRecords.length ? `今天已有 ${todayRecords.length} 条记录，覆盖 ${kinds.size} 类观察。` : "今天还没有记录，可从右下角添加第一条观察。",
      body: "汇总今天已经保存的客观记录。",
      tone: "summary",
      icon: "heart",
      details: [
        { label: "记录数量", value: `${todayRecords.length} 条` },
        { label: "覆盖类型", value: kinds.size ? Array.from(kinds).map((kind) => observationLabel[kind] ?? kind).join("、") : "暂无" },
        { label: "添加方式", value: "点击页面右下角“添加记录”，或在首页问答框直接描述多项记录。" },
      ],
    },
    {
      id: "profile-activity",
      title: "活动与步数",
      tag: "日常活动",
      preview: `最近步数 ${latestValue(records, "steps", "步")}。只显示设备或本人已经记录的活动。`,
      body: "呈现最近一次活动记录，不推断运动效果。",
      tone: "action",
      icon: "activity",
      trend: metricTrend(records, "steps", "步数变化", "步", "bar", "#4D8A82"),
      details: [
        { label: "最近步数", value: latestValue(records, "steps", "步") },
        { label: "记录原则", value: "只保留实际步数和时间，不据此评价体能。" },
      ],
    },
    {
      id: "profile-water",
      title: "饮水记录",
      tag: "生活记录",
      preview: `最近饮水 ${latestValue(records, "water_ml", "ml")}。多次饮水会分别保存，不自动补齐目标。`,
      body: "记录本人报告或设备同步的饮水量。",
      tone: "population",
      icon: "water",
      trend: metricTrend(records, "water_ml", "饮水变化", "ml", "bar", "#3F7FD7"),
      details: [
        { label: "最近饮水", value: latestValue(records, "water_ml", "ml") },
        { label: "数据边界", value: "未记录保持为空，不根据其他数据估算。" },
      ],
    },
    {
      id: "profile-sleep",
      title: "睡眠记录",
      tag: "休息节律",
      preview: `最近睡眠 ${latestValue(records, "sleep_minutes", "分钟")}。展示时长与记录时间，不判断睡眠疾病。`,
      body: "整理睡眠时长记录和来源。",
      tone: "action",
      icon: "sleep",
      trend: metricTrend(records, "sleep_minutes", "睡眠时长变化", "分钟", "bar", "#6687AF"),
      details: [
        { label: "最近睡眠", value: latestValue(records, "sleep_minutes", "分钟") },
        { label: "不能判断", value: "单次时长不能用于诊断睡眠障碍。" },
      ],
    },
    {
      id: "profile-body",
      title: "身体测量",
      tag: "体重 · 腰围",
      preview: `体重 ${latestValue(records, "weight_kg", "kg")}；腰围 ${latestValue(records, "waist_cm", "cm")}。`,
      body: "只展示本人或设备记录的身体测量数值。",
      tone: "population",
      icon: "body",
      trend: metricTrend(records, "weight_kg", "体重变化", "kg", "line", "#4D8A82"),
      details: [
        { label: "最近体重", value: latestValue(records, "weight_kg", "kg") },
        { label: "最近腰围", value: latestValue(records, "waist_cm", "cm") },
        { label: "测量条件", value: "趋势比较时应尽量保持相近的测量条件。" },
      ],
    },
    {
      id: "profile-heart-mood",
      title: "心率与情绪",
      tag: "身体感受",
      preview: `静息心率 ${latestValue(records, "resting_heart_rate", "次/分")}；心情 ${latestValue(records, "mood_score", "/ 5")}。`,
      body: "将设备数值和本人主观评分分开保存。",
      tone: "summary",
      icon: "mood",
      trend: metricTrend(records, "resting_heart_rate", "静息心率变化", "次/分", "line", "#B87555"),
      details: [
        { label: "最近心率", value: latestValue(records, "resting_heart_rate", "次/分") },
        { label: "最近心情", value: latestValue(records, "mood_score", "/ 5") },
        { label: "来源区别", value: "心率可来自设备；心情评分属于本人记录。" },
      ],
    },
    {
      id: "profile-connect",
      title: "数据连接",
      tag: "手机健康软件",
      preview: deviceCount ? `已有 ${deviceCount} 条设备同步记录；连接状态和授权范围见卡流下方。` : "尚无设备同步记录；Apple、Android 与华为连接器均保留真实授权边界。",
      body: "手机健康平台必须由原生应用完成用户授权，网页不会伪装已连接。",
      tone: "boundary",
      icon: "connect",
      details: [
        { label: "设备记录", value: `${deviceCount} 条` },
        { label: "接入边界", value: "Apple 健康与 Android Health Connect 需要原生桥接；华为需要开发者配置。" },
        { label: "可用接口", value: "通用 HTTPS JSON 批量导入已就绪。" },
      ],
    },
  ];
}

export function HealthInsightFlow({ observations, appleImport, onAppleImportComplete, onObservationDeleted }: { observations: ObservationRecord[]; appleImport: CompletedAppleHealthImport | null; onAppleImportComplete: (result: CompletedAppleHealthImport) => void; onObservationDeleted: (id: string) => void }) {
  const [connectors, setConnectors] = useState<HealthConnector[]>([]);
  const [analysisCard, setAnalysisCard] = useState<ProfileAnalysisCard | null>(null);
  const [analysisSource, setAnalysisSource] = useState<"ai" | "deterministic_fallback" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState("");
  const [pairing, setPairing] = useState<PairingSession | null>(null);
  const [pairingQr, setPairingQr] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { getHealthConnectors().then(setConnectors).catch(() => setError("连接器列表暂时不可用。")); }, []);
  const recordCards = useMemo(() => observationCards(observations), [observations]);
  const baseCards = useMemo(() => functionalCards(observations), [observations]);
  const importCards = useMemo(() => appleImport ? [appleImportCard(appleImport)] : [], [appleImport]);
  const cards = [...baseCards, ...recordCards, ...importCards];

  const importAppleHealth = async (file: File) => {
    setImporting(true); setError(""); setImportMessage("正在安全上传，不会将整个文件读入浏览器内存…");
    try {
      let job = await startAppleHealthImport(file);
      while (job.status === "queued" || job.status === "running") {
        setImportMessage(job.processed_records ? `已流式检查 ${job.processed_records.toLocaleString()} 条记录…` : "已上传，正在后台流式解析…");
        await new Promise((resolve) => window.setTimeout(resolve, 750));
        job = await getAppleHealthImport(job.id);
      }
      if (job.status !== "completed" || !job.summary) throw new Error(job.error ?? "导入失败");
      setImportMessage(`导入完成：新增 ${job.summary.accepted} 条每日汇总，正在打印一张摘要卡。`);
      onAppleImportComplete({ jobId: job.id, summary: job.summary });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Apple 健康数据导入失败。");
      setImportMessage("");
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const generate = async () => {
    setLoading(true); setError("");
    try {
      const result = await analyzeHealthProfile();
      setAnalysisCard(result.cards[0] ?? null); setAnalysisSource(result.source);
    } catch { setError("暂时无法生成观察卡，请稍后重试。"); }
    finally { setLoading(false); }
  };

  const startPairing = async (connectorId: HealthConnector["id"]) => {
    setError("");
    try {
      const session = await createHealthPairing(connectorId);
      const qr = await QRCode.toDataURL(JSON.stringify({ pairing_url: session.pairing_url, token: session.token, connector_id: session.connector_id }), { width: 220, margin: 2 });
      setPairing(session); setPairingQr(qr);
      const poll = window.setInterval(async () => {
        try {
          const next = await getHealthPairing(session.id);
          setPairing(next);
          if (next.status !== "pending") window.clearInterval(poll);
        } catch { window.clearInterval(poll); }
      }, 2000);
      window.setTimeout(() => window.clearInterval(poll), 610000);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "无法创建配对二维码。 "); }
  };

  return (
    <section className="mt-6 rounded-[22px] border border-border-divider bg-white p-5 shadow-[0_12px_35px_rgba(35,50,48,0.035)] sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div><div className="flex items-center gap-2"><Bot size={19} className="text-brand" /><h2 className="text-base font-semibold text-text-primary">综合 AI 健康分析</h2></div><p className="mt-1.5 max-w-2xl text-sm leading-6 text-text-secondary">结合全部已保存数值，集中呈现趋势、需关注信号和生活建议；自由文本备注不会发送给 AI。</p></div>
        <button type="button" onClick={() => void generate()} disabled={loading} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-brand/90 disabled:opacity-60">{loading ? <LoaderCircle size={16} className="animate-spin" /> : <ShieldCheck size={16} />}{loading ? "正在整理" : "生成综合分析"}</button>
      </div>
      {analysisSource ? <p className="mt-3 text-xs text-text-secondary">{analysisSource === "ai" ? "由 AI 基于非文本记录生成" : "AI 暂不可用，已使用本地规则整理"}</p> : null}
      {error ? <p role="alert" className="mt-3 text-sm text-risk-refused">{error}</p> : null}
      {analysisCard ? <div className="mt-5"><ComprehensiveHealthCard card={analysisCard} source={analysisSource ?? undefined} /></div> : null}
      <MedicalEvidenceCardFlow key="profile-health-flow" cards={cards} initialDisplay="instant" noun="观察卡" ariaLabel="健康观察卡拍立得与 Cover Flow" canDeleteCard={(card) => card.id.startsWith("observation:")} onDeleteCard={async (card) => { const id = card.id.replace("observation:", ""); await deleteObservation(id); onObservationDeleted(id); }} />
      <div className="mt-6 border-t border-border-divider pt-5">
        <div className="flex items-center gap-2"><Cable size={17} className="text-brand" /><h3 className="text-sm font-semibold text-text-primary">连接健康软件</h3></div><p className="mt-1 text-xs text-text-secondary">连接器只声明真实接入条件；授权令牌和平台密钥只由手机端或后端保存。</p>
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">{connectors.map((connector) => { const Icon = connectorIcon(connector.id); return <article key={connector.id} className="rounded-[16px] border border-border-divider bg-[#FBFCFC] p-4"><div className="flex items-center gap-2"><span className="grid h-9 w-9 place-items-center rounded-xl bg-white text-brand shadow-sm"><Icon size={18} /></span><h4 className="text-sm font-medium text-text-primary">{connector.label}</h4></div><p className={`mt-3 text-xs ${connector.status === "available" ? "text-brand" : "text-text-secondary"}`}>{statusLabel[connector.status]}</p><p className="mt-1.5 text-[11px] leading-5 text-text-secondary">{connector.authorization}</p>{connector.id !== "generic_import" ? <button type="button" onClick={() => void startPairing(connector.id)} className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-brand/20 bg-white px-3 py-2 text-xs font-medium text-brand hover:bg-brand/5"><Smartphone size={14} />扫码配对</button> : null}{connector.id === "apple_healthkit" ? <><input ref={fileInputRef} type="file" accept=".xml,text/xml,application/xml" className="sr-only" aria-label="选择 Apple 健康导出 XML" onChange={(event) => { const file = event.target.files?.[0]; if (file) void importAppleHealth(file); }} /><button type="button" disabled={importing} onClick={() => fileInputRef.current?.click()} className="mt-3 ml-2 inline-flex items-center gap-1.5 rounded-lg border border-brand/20 bg-white px-3 py-2 text-xs font-medium text-brand hover:bg-brand/5 disabled:opacity-60">{importing ? <LoaderCircle size={14} className="animate-spin" /> : <Upload size={14} />}{importing ? "正在导入" : "导入 XML"}</button></> : null}</article>; })}</div>
        {importMessage ? <p role="status" className="mt-3 text-xs text-brand">{importMessage}</p> : null}
        {pairing && pairingQr ? <div className="mt-4 flex flex-wrap items-center gap-4 rounded-xl border border-brand/20 bg-brand/5 p-4"><img src={pairingQr} alt="手机扫码配对健康数据" width={180} height={180} /><div className="text-xs leading-6 text-text-secondary"><p className="font-medium text-text-primary">请用手机同步 App 扫码</p><p>扫码后在手机系统授权健康数据，之后 App 可后台自动同步。</p><p className="mt-1 text-brand">状态：{pairing.status === "paired" ? "已配对" : pairing.status === "expired" ? "已过期" : "等待手机扫码"}</p></div></div> : null}
      </div>
    </section>
  );
}
