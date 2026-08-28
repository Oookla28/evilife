"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Printer, Sparkles, ChevronLeft, ChevronRight } from "lucide-react";
import { useCoverFlowControls } from "@/lib/motion/use-cover-flow-controls";

export interface EvidenceCardData {
  id: string;
  title: string;
  tag: string;
  evidenceStrength: "High" | "Medium" | "Low";
  summary: string;
  source: string;
  date: string;
}

const DEFAULT_CARDS: EvidenceCardData[] = [
  {
    id: "card-1",
    title: "地中海饮食与心血管",
    tag: "RCT 临床试验",
    evidenceStrength: "High",
    summary: "降低重大心血管事件风险约 30% (NEJM 权威研究)",
    source: "N Engl J Med (2018)",
    date: "2026-08-11"
  },
  {
    id: "card-2",
    title: "16:8 间歇性断食效应",
    tag: "队列分析",
    evidenceStrength: "Medium",
    summary: "有助于改善胰岛素敏感性，但减重效果与限制热量相当",
    source: "Cell Metab (2021)",
    date: "2026-08-10"
  }
];

const NEW_CARD_TEMPLATES: Omit<EvidenceCardData, "id" | "date">[] = [
  {
    title: "高盐饮食与血压关联",
    tag: "Meta 分析",
    evidenceStrength: "High",
    summary: "每日减少 3g 盐摄入可使收缩压平均下降 5.6 mmHg",
    source: "BMJ (2023)"
  },
  {
    title: "深海鱼油 Omega-3 补充",
    tag: "前瞻性研究",
    evidenceStrength: "Medium",
    summary: "对高甘油三酯人群有改善作用，普通健康人群预防效果有限",
    source: "JAMA (2022)"
  },
  {
    title: "黑咖啡与肝脏健康",
    tag: "观察性研究",
    evidenceStrength: "Medium",
    summary: "每日 2-3 杯黑咖啡与较低的脂肪肝及肝硬化风险显著相关",
    source: "Hepatology (2020)"
  }
];

export function PolaroidPrinterFlow() {
  const [cards, setCards] = useState<EvidenceCardData[]>(DEFAULT_CARDS);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const coverFlowControls = useCoverFlowControls({
    index: selectedIndex,
    count: cards.length,
    onIndexChange: setSelectedIndex,
  });
  const [isPrinting, setIsPrinting] = useState(false);
  const [printingCard, setPrintingCard] = useState<EvidenceCardData | null>(null);

  // Trigger printing a new card
  const handlePrintNew = () => {
    if (isPrinting) return;

    // Pick a template
    const template = NEW_CARD_TEMPLATES[cards.length % NEW_CARD_TEMPLATES.length];
    const newCardData: EvidenceCardData = {
      ...template,
      id: `card-${Date.now()}`,
      date: new Date().toISOString().split("T")[0]
    };

    setPrintingCard(newCardData);
    setIsPrinting(true);

    // Slow polaroid eject (~1.8s), then hand off into CoverFlow with no exit pause
    setTimeout(() => {
      setCards(prev => [newCardData, ...prev]);
      setSelectedIndex(0);
      // Drop overlay in the same tick — no fade/scale exit stutter
      setIsPrinting(false);
      setPrintingCard(null);
    }, 1800);
  };

  return (
    <div className="w-full max-w-2xl mx-auto my-8 flex flex-col items-center select-none">
      {/* Top Title & Trigger */}
      <div className="flex items-center justify-between w-full mb-4 px-2">
        <div className="flex items-center gap-2">
          <Printer size={18} className="text-brand" />
          <span className="font-bold text-text-primary text-base">拍立得打印机 & CoverFlow 证据流</span>
        </div>
        <button
          onClick={handlePrintNew}
          disabled={isPrinting}
          className="px-4 py-2 bg-brand text-white rounded-xl text-xs font-semibold hover:bg-brand/90 transition-all shadow-md active:scale-95 disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
        >
          {isPrinting ? <Sparkles size={14} className="animate-spin" /> : <Printer size={14} />}
          <span>{isPrinting ? "正在打印证据卡片..." : "打印新证据卡片"}</span>
        </button>
      </div>

      {/* Centered Polaroid Printer Hardware Component */}
      <div className="relative w-full bg-slate-100 rounded-3xl p-6 shadow-xl border border-slate-200 flex flex-col items-center overflow-hidden">
        {/* Printer Body Top Plate */}
        <div className="w-full bg-gradient-to-r from-slate-200 via-white to-slate-200 p-4 rounded-2xl border border-slate-300/80 shadow-md flex items-center justify-between relative z-20">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isPrinting ? "bg-amber-500 animate-ping" : "bg-emerald-500"}`} />
            <span className="text-xs font-mono font-bold text-slate-700">POLAROID EVIDENCE PRINTER</span>
          </div>
          <span className="text-[10px] font-mono text-slate-400">MODEL: EP-2026</span>
        </div>

        {/* Ejection Slot */}
        <div className="w-4/5 bg-slate-900 h-3 rounded-full shadow-inner my-1 border-b border-slate-400/40 relative z-20 flex items-center justify-center">
          <div className="w-11/12 h-1 bg-black rounded-full" />
        </div>

        {/* Ejection Printing Animation Area */}
        <div className="w-full relative min-h-[160px] flex items-start justify-center pt-2 overflow-hidden z-10">
          <AnimatePresence>
            {isPrinting && printingCard && (
              <motion.div
                initial={{ y: -160, opacity: 0.15, scale: 0.92 }}
                animate={{ y: 0, opacity: 1, scale: 1 }}
                // No fly-down / fade exit — card is already in CoverFlow when this unmounts
                exit={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0 } }}
                transition={{ duration: 1.8, ease: [0.22, 0.61, 0.36, 1] }}
                className="w-72 bg-white rounded-2xl p-4 border-2 border-brand/40 shadow-2xl flex flex-col gap-2 relative z-30"
              >
                <div className="flex justify-between items-center text-xs">
                  <span className="px-2 py-0.5 rounded bg-brand/10 text-brand font-bold text-[10px]">
                    {printingCard.tag}
                  </span>
                  <span className="text-[10px] text-text-secondary font-mono">PRINTING...</span>
                </div>
                <h4 className="font-bold text-sm text-text-primary leading-snug">{printingCard.title}</h4>
                <p className="text-xs text-text-secondary line-clamp-2">{printingCard.summary}</p>
                <div className="pt-2 border-t border-border-divider/60 flex justify-between items-center text-[10px] text-text-secondary">
                  <span>{printingCard.source}</span>
                  <span className="text-emerald-600 font-bold">已生成</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {!isPrinting && (
            <div className="text-xs text-text-secondary opacity-60 flex items-center gap-1.5 pt-8">
              <Sparkles size={14} className="text-brand" />
              点击顶部按钮，实时体验拍立得卡片出纸并自动滑落装载入 CoverFlow 3D 队列！
            </div>
          )}
        </div>

        {/* Integrated Apple CoverFlow 3D Deck */}
        <div className="w-full mt-4 pt-6 border-t border-slate-200/80 flex flex-col items-center">
          <div className="text-xs font-semibold text-text-secondary mb-4 flex items-center gap-2">
            <span>3D CoverFlow 证据卡片检索库 ({cards.length} 张卡片)</span>
          </div>

          {/* 3D Carousel Stage */}
          <motion.div
            drag="x"
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.16}
            dragMomentum={false}
            onDragEnd={(_, info) => coverFlowControls.onDragEnd(info)}
            onKeyDown={coverFlowControls.onKeyDown}
            onWheel={coverFlowControls.onWheel}
            role="region"
            aria-label="证据卡 CoverFlow，可左右拖动或使用方向键"
            tabIndex={0}
            whileDrag={{ cursor: "grabbing" }}
            className="relative w-full h-56 flex items-center justify-center perspective-[800px] overflow-hidden"
            style={{ touchAction: "pan-y", cursor: "grab" }}
          >
            {cards.map((card, index) => {
              const offset = index - selectedIndex;
              const isSelected = offset === 0;

              // CoverFlow 3D Transform calculations
              const rotateY = offset === 0 ? 0 : offset < 0 ? 45 : -45;
              const translateX = offset * 120;
              const translateZ = offset === 0 ? 50 : -100;
              const scale = offset === 0 ? 1 : 0.82;
              const opacity = Math.max(0.3, 1 - Math.abs(offset) * 0.35);

              return (
                <motion.div
                  key={card.id}
                  onClick={() => setSelectedIndex(index)}
                  initial={false}
                  animate={{
                    x: translateX,
                    z: translateZ,
                    rotateY: rotateY,
                    scale: scale,
                    opacity: opacity,
                  }}
                  // Avoid spring layout hitch when a freshly printed card lands in the deck
                  transition={isPrinting ? { duration: 0 } : { duration: 0.35, ease: "easeOut" }}
                  className={`absolute w-64 h-48 bg-white rounded-2xl p-4 border shadow-xl cursor-pointer flex flex-col justify-between transition-shadow hover:shadow-2xl ${
                    isSelected ? "border-brand ring-2 ring-brand/30 z-30" : "border-border-divider z-10"
                  }`}
                  style={{ transformStyle: "preserve-3d" }}
                >
                  <div className="flex flex-col gap-2">
                    <div className="flex justify-between items-center text-xs">
                      <span className="px-2 py-0.5 rounded bg-brand/10 text-brand font-bold text-[10px]">
                        {card.tag}
                      </span>
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700">
                        {card.evidenceStrength}
                      </span>
                    </div>
                    <h4 className="font-bold text-sm text-text-primary leading-tight">{card.title}</h4>
                    <p className="text-xs text-text-secondary leading-relaxed line-clamp-3">
                      {card.summary}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-border-divider/60 flex justify-between items-center text-[10px] text-text-secondary">
                    <span className="truncate max-w-[140px] font-mono">{card.source}</span>
                    <span className="font-mono">{card.date}</span>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>

          {/* CoverFlow Carousel Navigation Buttons */}
          <div className="flex items-center gap-4 mt-2 z-20">
            <button
              aria-label="上一张证据卡"
              onClick={() => setSelectedIndex(prev => Math.max(0, prev - 1))}
              disabled={selectedIndex === 0}
              className="p-2 rounded-full border border-border-divider bg-white hover:bg-black/5 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-xs font-mono text-text-secondary">
              {selectedIndex + 1} / {cards.length}
            </span>
            <button
              aria-label="下一张证据卡"
              onClick={() => setSelectedIndex(prev => Math.min(cards.length - 1, prev + 1))}
              disabled={selectedIndex === cards.length - 1}
              className="p-2 rounded-full border border-border-divider bg-white hover:bg-black/5 disabled:opacity-30 transition-colors"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
