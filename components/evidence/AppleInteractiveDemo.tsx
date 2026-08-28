"use client";

import { useState, useCallback, useRef, useEffect, type CSSProperties } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import {
  PassbookShredScene,
  SHRED_TOTAL_MS,
} from "@/components/evidence/PassbookShredScene";
import { useCoverFlowControls } from "@/lib/motion/use-cover-flow-controls";

const SPRING_FLOW = { type: "spring" as const, stiffness: 200, damping: 28 };
const SPRING_CARD = { type: "spring" as const, stiffness: 260, damping: 28 };
const SPRING_TRANSITION_IN = {
  type: "spring" as const,
  stiffness: 170,
  damping: 22,
  mass: 0.95,
};
/** 拍立得慢速出纸（模型等待窗） */
const PRINT_MS = 2400;
/** UICoverFlowLayer transitionIn:fromFrame: */
const TRANSITION_IN_MS = 620;
const SHRED_MS = SHRED_TOTAL_MS;
const CARD_W = 240;
const CARD_H = 170;

const CARD_COLORS = ["#1D3557", "#2D4A22", "#4A2040", "#2C3E50", "#5D3A1A"];
const SAMPLE_DATA = [
  { title: "地中海饮食与心血管", tag: "RCT 临床试验", body: "高质量证据：长期坚持可降低重大心血管事件风险约 30%。" },
  { title: "16:8 间歇断食效应", tag: "队列研究", body: "对胰岛素敏感性改善有统计学显著差异，减重效果与限热量相当。" },
  { title: "Omega-3 鱼油补充", tag: "Meta 分析", body: "高甘油三酯人群有效，普通人群心血管预防效果有限。" },
  { title: "黑咖啡与肝脏代谢", tag: "观察性研究", body: "每日 2–3 杯黑咖啡与较低脂肪肝和肝硬化风险显著关联。" },
  { title: "限钠饮食与血压调控", tag: "系统综述", body: "每日减少 3g 盐摄入可使收缩压平均下降 5.6 mmHg。" },
];

interface CardData {
  id: string;
  title: string;
  tag: string;
  body: string;
  colorIdx: number;
}

function CoverCard({
  card,
  flip,
  onFlip,
  style,
}: {
  card: CardData;
  flip: boolean;
  onFlip?: () => void;
  style?: CSSProperties;
}) {
  const bg = CARD_COLORS[card.colorIdx % CARD_COLORS.length];
  return (
    <div
      onClick={onFlip}
      className="w-full h-full relative cursor-pointer"
      style={{ perspective: 600, transformStyle: "preserve-3d", ...style }}
    >
      <motion.div
        animate={{ rotateY: flip ? 180 : 0 }}
        transition={SPRING_CARD}
        className="w-full h-full"
        style={{ transformStyle: "preserve-3d" }}
      >
        <div
          className="absolute inset-0 flex flex-col justify-between p-4"
          style={{
            background: bg,
            borderRadius: 14,
            backfaceVisibility: "hidden",
            boxShadow: "0 4px 20px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.12)",
          }}
        >
          <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-white/15 text-white/80 w-fit">
            {card.tag}
          </span>
          <div className="flex-1 flex flex-col justify-center gap-1 py-2">
            <h4 className="text-white font-bold text-[15px] leading-snug">{card.title}</h4>
            <p className="text-white/60 text-[11px] leading-relaxed line-clamp-3">{card.body}</p>
          </div>
          <div className="flex items-center gap-2 pt-2 border-t border-white/10">
            <div className="w-[6px] h-[6px] rounded-full bg-emerald-400" />
            <span className="text-[9px] text-white/40 font-mono">是非题 Evidence</span>
          </div>
        </div>
        <div
          className="absolute inset-0 flex flex-col justify-center items-center p-4"
          style={{
            background: bg,
            borderRadius: 14,
            backfaceVisibility: "hidden",
            transform: "rotateY(180deg)",
            boxShadow: "0 4px 20px rgba(0,0,0,.5)",
          }}
        >
          <span className="text-white/30 text-[10px] uppercase tracking-widest mb-2">BACK OF CARD</span>
          <span className="text-white/70 text-xs text-center">{card.title}</span>
          <span className="text-white/30 text-[10px] mt-3 font-mono">PMID: 29897866</span>
        </div>
      </motion.div>
    </div>
  );
}

export function AppleInteractiveDemo() {
  const [cards, setCards] = useState<CardData[]>([]);
  const [sel, setSel] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [phase, setPhase] = useState<
    "idle" | "printing" | "transitionIn" | "shredding"
  >("idle");
  const counterRef = useRef(0);
  const timersRef = useRef<number[]>([]);
  const [pendingCard, setPendingCard] = useState<CardData | null>(null);
  const [shredCard, setShredCard] = useState<CardData | null>(null);
  const [enteringId, setEnteringId] = useState<string | null>(null);

  useEffect(() => {
    const timers = timersRef.current;
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, []);

  const handleAdd = useCallback(() => {
    if (phase !== "idle") return;
    const idx = counterRef.current;
    const t = SAMPLE_DATA[idx % SAMPLE_DATA.length];
    const newCard: CardData = { id: `c${Date.now()}`, ...t, colorIdx: idx };
    counterRef.current++;
    setPendingCard(newCard);
    setPhase("printing");
    const tid = window.setTimeout(() => {
      setCards((prev) => [newCard, ...prev]);
      setFlipped(false);
      setSel(0);
      setPendingCard(null);
      setEnteringId(newCard.id);
      setPhase("transitionIn");
      const tid2 = window.setTimeout(() => {
        setEnteringId(null);
        setPhase("idle");
      }, TRANSITION_IN_MS);
      timersRef.current.push(tid2);
    }, PRINT_MS);
    timersRef.current.push(tid);
  }, [phase]);

  const handleDelete = useCallback(() => {
    if (phase !== "idle" || cards.length === 0) return;
    const target = cards[sel];
    if (!target) return;
    setShredCard(target);
    setPhase("shredding");
    setFlipped(false);
    const tid = window.setTimeout(() => {
      setCards((prev) => prev.filter((c) => c.id !== target.id));
      setSel((prev) => Math.max(0, Math.min(prev, cards.length - 2)));
      setShredCard(null);
      setPhase("idle");
    }, SHRED_MS);
    timersRef.current.push(tid);
  }, [phase, cards, sel]);

  const deckCards =
    phase === "shredding" && shredCard
      ? cards.filter((c) => c.id !== shredCard.id)
      : cards;

  const coverFlowControls = useCoverFlowControls({
    index: sel,
    count: deckCards.length,
    enabled: phase === "idle",
    onIndexChange: (next) => {
      setFlipped(false);
      setSel(next);
    },
  });

  return (
    <div className="w-full max-w-xl mx-auto flex flex-col items-center select-none">
      <div
        className="relative w-full overflow-hidden flex flex-col"
        style={{
          background: "#111",
          borderRadius: 24,
          minHeight: 460,
          boxShadow: "0 0 0 1px rgba(255,255,255,.06), 0 16px 48px rgba(0,0,0,.6)",
        }}
      >
        <div className="flex justify-center pt-4 pb-1 z-30">
          <div
            className="rounded-full"
            style={{
              width: "55%",
              height: 4,
              background:
                "linear-gradient(90deg,transparent,rgba(255,255,255,.18),transparent)",
              boxShadow:
                phase === "printing"
                  ? "0 0 16px 4px rgba(255,255,255,.32)"
                  : "inset 0 1px 2px rgba(0,0,0,.85)",
            }}
          />
        </div>

        <div
          className="relative flex-1 flex items-center justify-center px-4 overflow-hidden"
          style={{ minHeight: 300 }}
        >
          {deckCards.length === 0 &&
          phase !== "printing" &&
          phase !== "transitionIn" &&
          phase !== "shredding" ? (
            <div
              className="flex flex-col items-center justify-center text-center"
              style={{
                width: CARD_W,
                height: CARD_H,
                borderRadius: 14,
                border: "1.5px dashed rgba(255,255,255,.12)",
              }}
            >
              <Plus size={24} className="text-white/20 mb-2" />
              <span className="text-[11px] text-white/25">添加第一张卡片</span>
            </div>
          ) : (
            <motion.div
              drag={phase === "idle" ? "x" : false}
              dragConstraints={{ left: 0, right: 0 }}
              dragElastic={0.16}
              dragMomentum={false}
              onDragEnd={(_, info) => coverFlowControls.onDragEnd(info)}
              onKeyDown={coverFlowControls.onKeyDown}
              onWheel={coverFlowControls.onWheel}
              role="region"
              aria-label="证据卡 CoverFlow，可左右拖动或使用方向键"
              tabIndex={phase === "idle" ? 0 : -1}
              whileDrag={{ cursor: "grabbing" }}
              className="relative w-full flex items-center justify-center"
              style={{
                height: 250,
                perspective: 700,
                touchAction: "pan-y",
                cursor: phase === "idle" ? "grab" : "default",
                opacity:
                  phase === "shredding" ? 0 : phase === "printing" ? 0.35 : 1,
                pointerEvents: phase === "idle" ? "auto" : "none",
              }}
            >
              {deckCards.map((card, i) => {
                const off = i - sel;
                if (Math.abs(off) > 3) return null;
                const isCenter = off === 0;
                const ry = isCenter ? 0 : off < 0 ? 70 : -70;
                const tx = isCenter ? 0 : off * 85 + (off > 0 ? 30 : -30);
                const tz = isCenter ? 60 : -50;
                const sc = isCenter ? 1 : 0.75;
                const op = isCenter ? 1 : Math.max(0.4, 1 - Math.abs(off) * 0.25);
                const isEntering =
                  phase === "transitionIn" &&
                  card.id === enteringId &&
                  isCenter;
                return (
                  <motion.div
                    key={card.id}
                    initial={
                      isEntering
                        ? { x: 0, z: 6, rotateY: 0, scale: 0.97, opacity: 1 }
                        : false
                    }
                    animate={{ x: tx, z: tz, rotateY: ry, scale: sc, opacity: op }}
                    transition={
                      phase === "printing"
                        ? { duration: 0 }
                        : phase === "transitionIn"
                          ? SPRING_TRANSITION_IN
                          : SPRING_FLOW
                    }
                    onClick={() => {
                      if (!isCenter && phase === "idle") {
                        setFlipped(false);
                        setSel(i);
                      }
                    }}
                    className="absolute origin-center"
                    style={{
                      width: CARD_W,
                      height: CARD_H,
                      transformStyle: "preserve-3d",
                      zIndex: isCenter ? 20 : 10 - Math.abs(off),
                    }}
                  >
                    <CoverCard
                      card={card}
                      flip={isCenter && flipped && phase === "idle"}
                      onFlip={
                        isCenter && phase === "idle"
                          ? () => setFlipped((f) => !f)
                          : undefined
                      }
                    />
                  </motion.div>
                );
              })}
            </motion.div>
          )}

          <AnimatePresence>
            {phase === "printing" && pendingCard && (
              <motion.div
                key={pendingCard.id}
                initial={{ y: -175, opacity: 0.2, scale: 0.96 }}
                animate={{ y: 0, opacity: 1, scale: 1 }}
                exit={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0 } }}
                transition={{
                  duration: PRINT_MS / 1000,
                  ease: [0.22, 0.61, 0.36, 1],
                }}
                className="absolute z-40 pointer-events-none"
                style={{ width: CARD_W, height: CARD_H }}
              >
                <CoverCard card={pendingCard} flip={false} />
                <motion.div
                  initial={{ opacity: 0.5 }}
                  animate={{ opacity: 0 }}
                  transition={{ duration: PRINT_MS / 1000, ease: "easeOut" }}
                  style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: 14,
                    background:
                      "linear-gradient(180deg, rgba(255,255,255,.35), rgba(255,255,255,.05))",
                    mixBlendMode: "soft-light",
                    pointerEvents: "none",
                  }}
                />
              </motion.div>
            )}
          </AnimatePresence>

          {phase === "shredding" && shredCard && (
            <div className="absolute inset-0 z-50 flex items-center justify-center">
              <PassbookShredScene
                card={{
                  title: shredCard.title,
                  tag: shredCard.tag,
                  body: shredCard.body,
                  color: CARD_COLORS[shredCard.colorIdx % CARD_COLORS.length],
                }}
              />
            </div>
          )}
        </div>

        <div className="flex justify-center gap-1.5 pb-4">
          {cards.slice(0, 10).map((_, i) => (
            <div
              key={i}
              className="h-[5px] rounded-full bg-white"
              style={{ width: i === sel ? 14 : 5, opacity: i === sel ? 1 : 0.3 }}
            />
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3 mt-5">
        <button
          onClick={handleAdd}
          disabled={phase !== "idle"}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold disabled:opacity-35"
          style={{ background: "#007AFF", color: "#fff" }}
        >
          <Plus size={16} />
          {phase === "printing"
            ? "出纸中…"
            : phase === "transitionIn"
              ? "入库中…"
              : "添加"}
        </button>
        <button
          onClick={handleDelete}
          disabled={phase !== "idle" || cards.length === 0}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold disabled:opacity-35"
          style={{ background: "rgba(255,59,48,.12)", color: "#FF3B30" }}
        >
          <Trash2 size={16} />
          {phase === "shredding" ? "锯碎中…" : "删除"}
        </button>
        {cards.length > 1 && phase === "idle" && (
          <>
            <button
              aria-label="上一张证据卡"
              onClick={() => {
                setFlipped(false);
                setSel((p) => Math.max(0, p - 1));
              }}
              className="p-2 rounded-full"
              style={{ background: "rgba(255,255,255,.08)" }}
            >
              <ChevronLeft size={14} color="#fff" />
            </button>
            <button
              aria-label="下一张证据卡"
              onClick={() => {
                setFlipped(false);
                setSel((p) => Math.min(cards.length - 1, p + 1));
              }}
              className="p-2 rounded-full"
              style={{ background: "rgba(255,255,255,.08)" }}
            >
              <ChevronRight size={14} color="#fff" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
