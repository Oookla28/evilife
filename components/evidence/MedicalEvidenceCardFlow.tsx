"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { createPortal } from "react-dom";
import {
  AnimatePresence,
  LayoutGroup,
  motion,
  useReducedMotion,
} from "framer-motion";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ExternalLink,
  LoaderCircle,
  Maximize2,
  Trash2,
  X,
} from "lucide-react";
import {
  PassbookShredScene,
  SHRED_TOTAL_MS,
} from "@/components/evidence/PassbookShredScene";
import type {
  MedicalCardIcon,
  MedicalCardTone,
  MedicalFlowCard,
} from "@/lib/evidence/build-medical-flow-cards";
import { useCoverFlowControls } from "@/lib/motion/use-cover-flow-controls";
import { MedicalCardTrendPanel, TrendSparkline } from "@/components/evidence/MedicalCardTrendPanel";

const PRINT_MS = 1500;
const TRANSITION_IN_MS = 560;
const CARD_W = 292;
const CARD_H = 208;

const SPRING_FLOW = { type: "spring" as const, stiffness: 210, damping: 30 };
const SPRING_TRANSITION_IN = {
  type: "spring" as const,
  stiffness: 175,
  damping: 24,
  mass: 0.95,
};
const SPRING_FLIP = { type: "spring" as const, stiffness: 230, damping: 28 };

const CARD_STYLE: Record<
  MedicalCardTone,
  { accent: string; icon: MedicalCardIcon }
> = {
  summary: { accent: "#536AA6", icon: "heart" },
  support: { accent: "#72B875", icon: "check" },
  population: { accent: "#72B875", icon: "activity" },
  boundary: { accent: "#D3B838", icon: "shield" },
  action: { accent: "#54A8D2", icon: "check" },
};

// iPhone 5c color energy, softened with MacBook Neo's indigo, blush,
// citrus and silver so the index stays colorful while the reading face stays white.
const APPLE_CARD_PALETTE = {
  blue: "#54A8D2",
  green: "#72B875",
  blush: "#D98C98",
  citrus: "#D3B838",
  indigo: "#536AA6",
} as const;

function cardAccent(card: MedicalFlowCard) {
  if (card.icon === "tcm" || /mood/i.test(card.id)) return APPLE_CARD_PALETTE.blush;
  if (card.icon === "water" || card.icon === "connect") return APPLE_CARD_PALETTE.blue;
  if (card.icon === "sleep" || card.icon === "activity") return APPLE_CARD_PALETTE.indigo;
  if (card.icon === "body") return APPLE_CARD_PALETTE.green;
  if (card.tone === "boundary") return APPLE_CARD_PALETTE.citrus;
  return CARD_STYLE[card.tone].accent;
}

type Phase = "printing" | "transitionIn" | "idle" | "shredding";
type IndexSide = "left" | "right";

function indexSideForOffset(offset: number): IndexSide {
  void offset;
  return "left";
}

function CardIndexIcon({ icon }: { icon: MedicalCardIcon }) {
  const p = { fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return <svg viewBox="0 0 24 24" aria-hidden="true" className="h-7 w-7 text-white drop-shadow-[0_1px_1px_rgba(0,0,0,.14)]">
    {icon === "heart" ? <><path {...p} d="M20.5 5.8c-2.2-2.3-5.9-1.6-7.4 1L12 8.2l-1.1-1.4c-1.6-2.6-5.3-3.3-7.4-1C.8 8.6 2.4 13 5 15.5L12 22l7-6.5c2.6-2.5 4.2-6.9 1.5-9.7Z" /><path {...p} d="M5.5 12h3l1.3-2.8 2.1 6 1.6-3.2h4.9" /></> : null}
    {icon === "activity" ? <><circle {...p} cx="12" cy="12" r="8.5" /><path {...p} d="M4.7 9.4h3.1l1.8-3.2 3.3 11.2 2.1-5h4.1" /></> : null}
    {icon === "water" ? <><path {...p} d="M12 2.5S5.8 9.5 5.8 14.4a6.2 6.2 0 0 0 12.4 0C18.2 9.5 12 2.5 12 2.5Z" /><path {...p} d="M9 16.2c.7 1.2 1.7 1.8 3.1 1.8" /></> : null}
    {icon === "sleep" ? <><path {...p} d="M19.5 15.4A8.2 8.2 0 0 1 8.6 4.5 8.4 8.4 0 1 0 19.5 15.4Z" /><path {...p} d="M15.5 5.2h4l-4 4h4" /></> : null}
    {icon === "body" ? <><rect {...p} x="4" y="5" width="16" height="15" rx="3" /><path {...p} d="M9 9.5a3 3 0 0 1 6 0m-3 0L14 8" /></> : null}
    {icon === "mood" ? <><circle {...p} cx="12" cy="12" r="9" /><path {...p} d="M8.5 10h.01M15.5 10h.01M8.2 14.2c1.1 1.3 2.4 1.9 3.8 1.9s2.7-.6 3.8-1.9" /></> : null}
    {icon === "connect" ? <><path {...p} d="M9.4 14.6 7.8 16.2a3.4 3.4 0 1 1-4.8-4.8l3.2-3.2A3.4 3.4 0 0 1 11 8m3.6 1.4 1.6-1.6a3.4 3.4 0 1 1 4.8 4.8l-3.2 3.2A3.4 3.4 0 0 1 13 16m-4.5-.5 7-7" /></> : null}
    {icon === "tcm" ? <><path {...p} d="M19.5 4.5C12 4.7 6.4 8.2 5.3 13.8c-.5 2.7.8 4.9 3.3 5.7 2.5.8 5.4-.2 6.8-2.5 2.2-3.6 2.2-7.7 4.1-12.5Z" /><path {...p} d="M5 20c2.7-4.4 6-7.4 10.2-9.2M9.2 15.4c1.3.1 2.5.4 3.5 1" /></> : null}
    {icon === "shield" ? <><path {...p} d="M12 2.5 20 6v5.5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-3.5Z" /><path {...p} d="M12 8v5m0 3.5h.01" /></> : null}
    {icon === "check" ? <><circle {...p} cx="12" cy="12" r="9" /><path {...p} d="m8 12.2 2.7 2.7 5.5-6" /></> : null}
    {icon === "note" ? <><path {...p} d="M6 3h9l3 3v15H6z" /><path {...p} d="M15 3v4h4M9 11h6M9 15h6" /></> : null}
  </svg>;
}

function ColoredIndex({
  card,
  side,
}: {
  card: MedicalFlowCard;
  side: IndexSide;
}) {
  const { icon } = CARD_STYLE[card.tone];
  const accent = cardAccent(card);
  return (
    <div
      aria-hidden="true"
      className={`absolute inset-y-[7px] flex w-[15%] items-center justify-center ${
        side === "left"
          ? "left-[7px] rounded-l-[15px] rounded-r-[5px]"
          : "right-[7px] rounded-l-[5px] rounded-r-[15px]"
      }`}
      style={{ backgroundColor: accent }}
    >
      <CardIndexIcon icon={card.icon ?? icon} />
    </div>
  );
}

function FaceContent({
  card,
  side,
  back,
  onExpand,
  scrollRef,
}: {
  card: MedicalFlowCard;
  side: IndexSide;
  back: boolean;
  onExpand: () => void;
  scrollRef?: RefObject<HTMLDivElement | null>;
}) {
  const accent = cardAccent(card);
  const contentInset = side === "left" ? "pl-[61px] pr-[38px]" : "pl-[38px] pr-[61px]";

  return (
    <article
      className={`absolute inset-0 overflow-hidden rounded-[19px] border border-[#D9D9DE] bg-white ${contentInset}`}
      style={{
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
        boxShadow:
          "0 18px 42px rgba(30,35,45,.13), 0 2px 7px rgba(30,35,45,.08), inset 0 1px 0 #fff",
        transform: back ? "rotateY(180deg)" : undefined,
      }}
    >
      <ColoredIndex card={card} side={side} />
      {back ? (
        <div className="flex h-full min-h-0 flex-col py-4">
          <div className="mb-2 flex items-center justify-between border-b border-[#E9E9ED] pb-2">
            <div>
              <p className="text-[9px] font-semibold tracking-[0.08em] text-[#86868B]">
                详细说明
              </p>
              <h4 className="mt-0.5 text-[14px] font-semibold leading-tight tracking-[-0.015em] text-[#1D1D1F]">
                {card.title}
              </h4>
            </div>
            <button
              type="button"
              aria-label={`放大查看${card.title}`}
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                onExpand();
              }}
              className="rounded-full border border-[#D9D9DE] bg-white p-1.5 text-[#6E6E73] shadow-sm transition-[transform,background-color] hover:bg-[#F5F5F7] active:scale-95"
            >
              <Maximize2 size={12} strokeWidth={1.8} />
            </button>
          </div>
          <div
            ref={scrollRef}
            className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            {card.trend ? <TrendSparkline trend={card.trend} /> : null}
            {card.details.map((detail) => (
              <div key={detail.label} className="grid grid-cols-[66px_1fr] gap-2">
                <span className="text-[9px] font-semibold leading-[1.45]" style={{ color: accent }}>
                  {detail.label}
                </span>
                <p className="whitespace-pre-line text-[9.5px] leading-[1.5] text-[#515154]">
                  {detail.value}
                </p>
              </div>
            ))}
            {(card.sourceLinks ?? (card.sourceUrl ? [{ label: "查看原始来源", url: card.sourceUrl }] : [])).map((source) => (
              <a
                key={`${source.url}-${source.label}`}
                href={source.url}
                target="_blank"
                rel="noreferrer"
                aria-label={`查看原始来源：${source.label}`}
                onPointerDown={(event) => event.stopPropagation()}
                onClick={(event) => event.stopPropagation()}
                className="flex items-center justify-between gap-1 rounded-lg border border-[#D9D9DE] bg-white px-2.5 py-1.5 text-[9px] font-semibold leading-snug text-[#536AA6] transition-colors hover:bg-[#F5F5F7]"
              >
                <span className="line-clamp-2">{source.label}</span>
                <ExternalLink size={10} className="shrink-0" strokeWidth={1.8} />
              </a>
            ))}
          </div>
          <div className="mt-2 flex items-center justify-center gap-1 text-[9px] text-[#86868B]">
            <ChevronDown size={11} strokeWidth={1.8} />
            点击卡片返回正面
          </div>
        </div>
      ) : (
        <div className="flex h-full flex-col py-4">
          <p className="text-[9px] font-semibold tracking-[0.08em]" style={{ color: accent }}>
            {card.tag}
          </p>
          <div
            ref={scrollRef}
            className="my-3 min-h-0 flex-1 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            <h4 className="mb-2 text-[17px] font-semibold leading-tight tracking-[-0.025em] text-[#1D1D1F]">
              {card.title}
            </h4>
            <p className="text-[11px] leading-[1.6] text-[#6E6E73]">
              {card.preview}
            </p>
          </div>
          <div className="flex items-center justify-center gap-1 border-t border-[#ECECF0] pt-2 text-[9px] text-[#86868B]">
            <ChevronUp size={11} strokeWidth={1.8} />
            点击卡片查看详情
          </div>
        </div>
      )}
    </article>
  );
}

function PullRail({
  card,
  scrollRef,
}: {
  card: MedicalFlowCard;
  scrollRef: RefObject<HTMLDivElement | null>;
}) {
  const accent = cardAccent(card);
  const scrollText = (delta: number) => {
    scrollRef.current?.scrollBy({ top: delta, behavior: "smooth" });
  };

  return (
    <div
      className="absolute inset-y-[11px] right-[8px] z-20 flex w-[22px] flex-col items-center justify-between"
      aria-label={`${card.title}文字滚动控制`}
    >
      <button
        type="button"
        aria-label={`向上滚动${card.title}文字`}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
          scrollText(-52);
        }}
        className="relative z-10 rounded-full p-0.5 text-[#8E8E93] transition-colors hover:bg-[#EEEEF2] hover:text-[#515154] active:text-[#1D1D1F]"
      >
        <ChevronUp size={12} strokeWidth={1.8} />
      </button>
      <div className="absolute inset-y-4 left-1/2 w-px -translate-x-1/2 bg-[#E0E0E5]" />
      <motion.button
        type="button"
        aria-label={`拖动滚动${card.title}文字`}
        title="拖动控制文字上下滚动"
        drag="y"
        dragConstraints={{ top: -48, bottom: 48 }}
        dragElastic={0.04}
        dragMomentum={false}
        dragSnapToOrigin
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
        }}
        onDrag={(event, info) => {
          event.stopPropagation();
          if (scrollRef.current) scrollRef.current.scrollTop += info.delta.y * 2.2;
        }}
        whileTap={{ scale: 0.94 }}
        className="relative z-10 h-10 w-3.5 cursor-ns-resize rounded-full border-2 border-white shadow-[0_1px_4px_rgba(0,0,0,.18)] outline-none ring-offset-2 focus-visible:ring-2"
        style={{ backgroundColor: accent, color: accent }}
      />
      <button
        type="button"
        aria-label={`向下滚动${card.title}文字`}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => {
          event.stopPropagation();
          scrollText(52);
        }}
        className="relative z-10 rounded-full p-0.5 text-[#8E8E93] transition-colors hover:bg-[#EEEEF2] hover:text-[#515154] active:text-[#1D1D1F]"
      >
        <ChevronDown size={12} strokeWidth={1.8} />
      </button>
    </div>
  );
}

function MedicalCard({
  card,
  side,
  flipped,
  onExpand,
}: {
  card: MedicalFlowCard;
  side: IndexSide;
  flipped: boolean;
  onExpand: () => void;
}) {
  const previewScrollRef = useRef<HTMLDivElement>(null);
  const detailScrollRef = useRef<HTMLDivElement>(null);

  return (
    <div className="relative h-full w-full" style={{ transformStyle: "preserve-3d" }}>
      <motion.div
        className="absolute inset-0"
        animate={{ rotateY: flipped ? 180 : 0 }}
        transition={SPRING_FLIP}
        style={{ transformStyle: "preserve-3d" }}
      >
        <FaceContent
          card={card}
          side={side}
          back={false}
          onExpand={onExpand}
          scrollRef={previewScrollRef}
        />
        <FaceContent
          card={card}
          side={side}
          back
          onExpand={onExpand}
          scrollRef={detailScrollRef}
        />
      </motion.div>
      <PullRail card={card} scrollRef={flipped ? detailScrollRef : previewScrollRef} />
    </div>
  );
}

function ExpandedCard({ card, onClose }: { card: MedicalFlowCard; onClose: () => void }) {
  const { icon } = CARD_STYLE[card.tone];
  const accent = cardAccent(card);
  return (
    <motion.div
      layoutId={`medical-card-${card.id}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby={`expanded-${card.id}`}
      onClick={(event) => event.stopPropagation()}
      className={`relative flex max-h-[min(760px,calc(100vh-32px))] w-full overflow-hidden rounded-[24px] border border-[#D2D2D7] bg-white shadow-[0_28px_90px_rgba(0,0,0,.24)] ${card.trend ? "max-w-[980px]" : "max-w-[700px]"}`}
    >
      <div
        className="flex w-[15%] min-w-[62px] items-center justify-center"
        style={{ backgroundColor: accent }}
      >
        <CardIndexIcon icon={card.icon ?? icon} />
      </div>
      <div className="min-w-0 flex-1 overflow-y-auto p-5 [scrollbar-width:none] sm:p-7 [&::-webkit-scrollbar]:hidden">
        <div className="flex items-start justify-between gap-4 border-b border-[#E8E8ED] pb-4">
          <div>
            <p className="text-[11px] font-semibold tracking-[0.08em]" style={{ color: accent }}>
              {card.tag} · 详细说明
            </p>
            <h3
              id={`expanded-${card.id}`}
              className="mt-1 text-xl font-semibold tracking-[-0.025em] text-[#1D1D1F] sm:text-2xl"
            >
              {card.title}
            </h3>
          </div>
          <button
            type="button"
            aria-label="关闭放大证据卡"
            onClick={onClose}
            className="shrink-0 rounded-full bg-[#F2F2F7] p-2 text-[#515154] transition-transform hover:bg-[#E8E8ED] active:scale-95"
          >
            <X size={17} strokeWidth={1.8} />
          </button>
        </div>
        {card.trend ? <MedicalCardTrendPanel trend={card.trend} /> : null}
        <div className="divide-y divide-[#ECECF0]">
          {card.details.map((detail) => (
            <div key={detail.label} className="grid gap-1 py-4 sm:grid-cols-[128px_1fr] sm:gap-5">
              <h4 className="text-[13px] font-semibold" style={{ color: accent }}>
                {detail.label}
              </h4>
              <p className="whitespace-pre-line text-[14px] leading-[1.7] text-[#515154]">
                {detail.value}
              </p>
            </div>
          ))}
        </div>
        {(card.sourceLinks?.length || card.sourceUrl) ? (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {(card.sourceLinks ?? [{ label: "查看原始来源", url: card.sourceUrl! }]).map((source) => (
              <a
                key={`${source.url}-${source.label}`}
                href={source.url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between gap-2 rounded-xl border border-[#D2D2D7] bg-white px-3 py-2 text-xs font-semibold leading-snug text-[#536AA6] transition-colors hover:bg-[#F5F5F7]"
              >
                <span>{source.label}</span>
                <ExternalLink size={13} className="shrink-0" strokeWidth={1.8} />
              </a>
            ))}
          </div>
        ) : null}
        <p className="mt-3 text-[11px] leading-relaxed text-[#86868B]">
          是非题提供证据概括，不替代专业医疗诊断或个体化治疗建议。
        </p>
      </div>
    </motion.div>
  );
}

interface MedicalEvidenceCardFlowProps {
  cards: MedicalFlowCard[];
  noun?: string;
  ariaLabel?: string;
  initialDisplay?: "print" | "instant";
  canDeleteCard?: (card: MedicalFlowCard) => boolean;
  onDeleteCard?: (card: MedicalFlowCard) => Promise<void> | void;
}

export function MedicalEvidenceCardFlow({
  cards,
  noun = "证据卡",
  ariaLabel = "医疗证据卡生成流程",
  initialDisplay = "print",
  canDeleteCard = () => true,
  onDeleteCard,
}: MedicalEvidenceCardFlowProps) {
  const reduceMotion = useReducedMotion();
  const revealInitially = initialDisplay === "instant" || Boolean(reduceMotion);
  const [deck, setDeck] = useState<MedicalFlowCard[]>(() => revealInitially ? cards : []);
  const [printQueue, setPrintQueue] = useState<MedicalFlowCard[]>(() => revealInitially ? [] : cards);
  const [cursor, setCursor] = useState(0);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>(() =>
    revealInitially || cards.length === 0 ? "idle" : "printing"
  );
  const [enteringId, setEnteringId] = useState<string | null>(null);
  const [flippedIds, setFlippedIds] = useState<Set<string>>(() => new Set());
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [shredCard, setShredCard] = useState<MedicalFlowCard | null>(null);
  const timersRef = useRef<number[]>([]);
  const knownIdsRef = useRef(new Set(cards.map((card) => card.id)));
  const phaseRef = useRef<Phase>(phase);
  const cardsRef = useRef(cards);
  const deckLengthRef = useRef(deck.length);
  const pendingCard = printQueue[cursor] ?? null;

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((timer) => window.clearTimeout(timer));
    timersRef.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  useEffect(() => {
    cardsRef.current = cards;
    deckLengthRef.current = deck.length;
  }, [cards, deck.length]);

  useEffect(() => {
    const incomingIds = new Set(cards.map((card) => card.id));
    const incomingById = new Map(cards.map((card) => [card.id, card]));
    const additions = cards.filter((card) => !knownIdsRef.current.has(card.id));
    knownIdsRef.current = incomingIds;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      if (reduceMotion) {
        setDeck(cards);
        if (additions.length) {
          setSelectedIndex(Math.max(0, cards.findIndex((card) => card.id === additions[0]?.id)));
        } else {
          setSelectedIndex((previous) => Math.max(0, Math.min(previous, cards.length - 1)));
        }
        setPhase("idle");
        return;
      }
      setDeck((previous) => previous
        .filter((card) => incomingIds.has(card.id))
        .map((card) => incomingById.get(card.id) ?? card));
      if (!additions.length) return;
      if (phaseRef.current === "idle") {
        setPrintQueue(additions);
        setCursor(0);
        setPhase("printing");
      } else {
        setPrintQueue((previous) => [...previous, ...additions]);
      }
    });
    return () => { cancelled = true; };
  }, [cards, reduceMotion]);

  useEffect(() => {
    if (reduceMotion || phase !== "printing" || !pendingCard) return;
    const timer = window.setTimeout(() => {
      setDeck((previous) => [...previous, pendingCard]);
      setSelectedIndex(deckLengthRef.current);
      setEnteringId(pendingCard.id);
      setPhase("transitionIn");
    }, PRINT_MS);
    timersRef.current.push(timer);
    return () => window.clearTimeout(timer);
  }, [cursor, pendingCard, phase, reduceMotion]);

  useEffect(() => {
    if (reduceMotion || phase !== "transitionIn") return;
    const timer = window.setTimeout(() => {
      setEnteringId(null);
      if (cursor + 1 < printQueue.length) {
        setCursor((previous) => previous + 1);
        setPhase("printing");
      } else {
        const finalCards = cardsRef.current;
        setDeck((previous) => {
          const available = new Map(previous.map((card) => [card.id, card]));
          return finalCards.map((card) => available.get(card.id) ?? card);
        });
        setSelectedIndex(Math.max(0, finalCards.findIndex((card) => card.id === pendingCard?.id)));
        setPhase("idle");
      }
    }, TRANSITION_IN_MS);
    timersRef.current.push(timer);
    return () => window.clearTimeout(timer);
  }, [cursor, pendingCard?.id, phase, printQueue.length, reduceMotion]);

  useEffect(() => {
    if (!expandedId) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpandedId(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expandedId]);

  const visibleDeck = useMemo(
    () =>
      phase === "shredding" && shredCard
        ? deck.filter((card) => card.id !== shredCard.id)
        : deck,
    [deck, phase, shredCard]
  );

  const controls = useCoverFlowControls({
    index: selectedIndex,
    count: visibleDeck.length,
    enabled: phase === "idle" && !expandedId,
    onIndexChange: setSelectedIndex,
  });

  const setCardFlipped = useCallback((id: string, flipped: boolean) => {
    setFlippedIds((current) => {
      const next = new Set(current);
      if (flipped) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const handleDelete = useCallback(() => {
    if (phase !== "idle") return;
    const target = deck[selectedIndex];
    if (!target) return;
    setExpandedId(null);
    setShredCard(target);
    setPhase("shredding");

    const finish = async () => {
      try {
        await onDeleteCard?.(target);
      } catch {
        setShredCard(null);
        setPhase("idle");
        return;
      }
      setDeck((previous) => previous.filter((card) => card.id !== target.id));
      setSelectedIndex((previous) => Math.max(0, Math.min(previous, deck.length - 2)));
      setFlippedIds((current) => {
        const next = new Set(current);
        next.delete(target.id);
        return next;
      });
      setShredCard(null);
      setPhase("idle");
    };

    if (reduceMotion) {
      void finish();
      return;
    }

    const timer = window.setTimeout(() => void finish(), SHRED_TOTAL_MS);
    timersRef.current.push(timer);
  }, [deck, onDeleteCard, phase, reduceMotion, selectedIndex]);

  if (!cards.length) return null;

  const queueTotal = Math.max(1, printQueue.length);
  const progress = phase === "idle" ? deck.length : Math.min(cursor + 1, queueTotal);
  const statusText =
    phase === "printing"
      ? `正在生成第 ${progress}/${queueTotal} 张新增中文${noun}`
      : phase === "transitionIn"
        ? `第 ${progress}/${queueTotal} 张已完成，正在放入 Flow`
        : phase === "shredding"
          ? `正在安全移除这张${noun}`
          : `${deck.length} 张中文${noun}已生成`;
  const expandedCard = deck.find((card) => card.id === expandedId) ?? null;
  const selectedCard = deck[selectedIndex] ?? null;

  return (
    <LayoutGroup id="medical-evidence-coverflow">
      <section
        data-testid="medical-card-flow"
        data-phase={phase}
        data-card-count={deck.length}
        className="mt-5 w-full select-none"
        aria-label={ariaLabel}
      >
        <div className="mb-2 flex items-center justify-between gap-3 px-1 text-xs text-text-secondary">
          <span className="flex items-center gap-2">
            {phase !== "idle" ? <LoaderCircle size={14} className="animate-spin text-brand" /> : null}
            {statusText}
          </span>
          <span className="font-mono text-[10px] text-text-secondary/70">拍立得 → Flow</span>
        </div>

        <div className="relative min-h-[438px] overflow-hidden rounded-[28px] border border-[#DEDFDF] bg-[#F3F3F0] shadow-[0_16px_48px_rgba(32,35,45,.09)]">
          <div className="relative z-30 flex justify-center pt-4">
            <div
              className="h-1.5 w-[48%] max-w-[300px] rounded-full bg-[#D1D1D6] shadow-[inset_0_1px_2px_rgba(0,0,0,.18)]"
              style={{
                boxShadow:
                  phase === "printing"
                    ? "0 0 0 4px rgba(255,255,255,.75), inset 0 1px 2px rgba(0,0,0,.18)"
                    : "inset 0 1px 2px rgba(0,0,0,.18)",
              }}
            />
          </div>

          <div className="relative flex min-h-[350px] items-center justify-center overflow-hidden px-2 pt-2 sm:px-3">
            <motion.div
              drag={phase === "idle" && !expandedId ? "x" : false}
              dragConstraints={{ left: 0, right: 0 }}
              dragElastic={0.16}
              dragMomentum={false}
              onDragEnd={(_, info) => controls.onDragEnd(info)}
              onKeyDown={controls.onKeyDown}
              onWheel={controls.onWheel}
              role="region"
              aria-label={`${ariaLabel}，可左右拖动、滚轮切换或使用方向键`}
              tabIndex={phase === "idle" ? 0 : -1}
              className="relative flex h-[292px] w-full items-center justify-center outline-none focus-visible:ring-2 focus-visible:ring-[#3F7C78]/45"
              style={{
                perspective: 820,
                touchAction: "pan-y",
                cursor: phase === "idle" ? "grab" : "default",
                opacity: phase === "printing" ? 0.32 : phase === "shredding" ? 0 : 1,
                pointerEvents: phase === "idle" ? "auto" : "none",
              }}
              whileDrag={{ cursor: "grabbing" }}
            >
              {visibleDeck.map((card, index) => {
                const offset = index - selectedIndex;
                if (Math.abs(offset) > 3) return null;
                const isCenter = offset === 0;
                const isEntering = phase === "transitionIn" && card.id === enteringId;
                const rotateY = isCenter ? 0 : offset < 0 ? 70 : -70;
                const translateX = isCenter ? 0 : offset * 96 + (offset > 0 ? 42 : -42);
                const side = indexSideForOffset(offset);
                const flipped = flippedIds.has(card.id);

                return (
                  <motion.div
                    key={card.id}
                    layoutId={`medical-card-${card.id}`}
                    data-card-id={card.id}
                    data-card-side={side}
                    data-flipped={flipped ? "true" : "false"}
                    initial={
                      isEntering
                        ? { x: 0, z: 4, rotateY: 0, scale: 0.97, opacity: 1 }
                        : false
                    }
                    animate={{
                      x: translateX,
                      z: isCenter ? 72 : -68,
                      rotateY,
                      scale: isCenter ? 1 : 0.74,
                      opacity: isCenter ? 1 : Math.max(0.38, 1 - Math.abs(offset) * 0.23),
                    }}
                    transition={
                      reduceMotion
                        ? { duration: 0 }
                        : phase === "transitionIn"
                          ? SPRING_TRANSITION_IN
                          : SPRING_FLOW
                    }
                    onClick={() => {
                      if (phase !== "idle") return;
                      if (isCenter) setCardFlipped(card.id, !flipped);
                      else setSelectedIndex(index);
                    }}
                    className="absolute origin-center"
                    style={{
                      width: CARD_W,
                      height: CARD_H,
                      transformStyle: "preserve-3d",
                      zIndex: isCenter ? 20 : 10 - Math.abs(offset),
                    }}
                  >
                    <MedicalCard
                      card={card}
                      side={side}
                      flipped={flipped}
                      onExpand={() => {
                        setSelectedIndex(index);
                        setExpandedId(card.id);
                      }}
                    />
                  </motion.div>
                );
              })}
            </motion.div>

            <AnimatePresence>
              {phase === "printing" && pendingCard ? (
                <motion.div
                  key={pendingCard.id}
                  initial={reduceMotion ? false : { y: -214, opacity: 0.12, scale: 0.96 }}
                  animate={{ y: 0, opacity: 1, scale: 1 }}
                  exit={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0 } }}
                  transition={{
                    duration: reduceMotion ? 0 : PRINT_MS / 1000,
                    ease: [0.22, 0.61, 0.36, 1],
                  }}
                  className="pointer-events-none absolute z-40"
                  style={{ width: CARD_W, height: CARD_H }}
                >
                  <MedicalCard
                    card={pendingCard}
                    side="left"
                    flipped={false}
                    onExpand={() => undefined}
                  />
                </motion.div>
              ) : null}
            </AnimatePresence>

            {phase === "shredding" && shredCard ? (
              <div className="absolute inset-0 z-50 flex items-center justify-center">
                <PassbookShredScene
                  card={{
                    title: shredCard.title,
                    tag: shredCard.tag,
                    body: shredCard.body,
                    color: cardAccent(shredCard),
                  }}
                />
              </div>
            ) : null}
          </div>

          <div className="absolute inset-x-0 bottom-4 z-30 flex items-center justify-center gap-2">
            <button
              type="button"
              aria-label={`上一张${noun}`}
              disabled={phase !== "idle" || selectedIndex === 0}
              onClick={() => setSelectedIndex((previous) => Math.max(0, previous - 1))}
              className="rounded-full border border-[#D8D8DD] bg-white p-2 text-[#515154] shadow-sm transition-[transform,background-color] hover:bg-[#FAFAFC] active:scale-95 disabled:opacity-25"
            >
              <ChevronLeft size={15} strokeWidth={1.8} />
            </button>
            <span className="min-w-12 text-center font-mono text-[10px] text-[#86868B]">
              {deck.length ? `${selectedIndex + 1}/${deck.length}` : `0/${cards.length}`}
            </span>
            <button
              type="button"
              aria-label={`下一张${noun}`}
              disabled={phase !== "idle" || selectedIndex >= deck.length - 1}
              onClick={() =>
                setSelectedIndex((previous) => Math.min(deck.length - 1, previous + 1))
              }
              className="rounded-full border border-[#D8D8DD] bg-white p-2 text-[#515154] shadow-sm transition-[transform,background-color] hover:bg-[#FAFAFC] active:scale-95 disabled:opacity-25"
            >
              <ChevronRight size={15} strokeWidth={1.8} />
            </button>
            <button
              type="button"
              aria-label={`放大当前${noun}`}
              disabled={phase !== "idle" || !selectedCard}
              onClick={() => selectedCard && setExpandedId(selectedCard.id)}
              className="ml-2 rounded-full border border-[#D8D8DD] bg-white p-2 text-[#3F7C78] shadow-sm transition-[transform,background-color] hover:bg-[#FAFAFC] active:scale-95 disabled:opacity-25"
            >
              <Maximize2 size={14} strokeWidth={1.8} />
            </button>
            <button
              type="button"
              aria-label={`用碎纸机移除当前${noun}`}
              disabled={phase !== "idle" || !selectedCard || !canDeleteCard(selectedCard)}
              onClick={handleDelete}
              className="rounded-full border border-[#E2CCCC] bg-white p-2 text-[#B45454] shadow-sm transition-[transform,background-color] hover:bg-[#FFF7F7] active:scale-95 disabled:opacity-25"
            >
              <Trash2 size={14} strokeWidth={1.8} />
            </button>
          </div>
        </div>
      </section>

      {typeof document !== "undefined"
        ? createPortal(
            <AnimatePresence>
              {expandedCard ? (
                <motion.div
                  key={expandedCard.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: reduceMotion ? 0 : 0.2 }}
                  onClick={() => setExpandedId(null)}
                  className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/25 p-4 backdrop-blur-[2px]"
                >
                  <ExpandedCard card={expandedCard} onClose={() => setExpandedId(null)} />
                </motion.div>
              ) : null}
            </AnimatePresence>,
            document.body
          )
        : null}
    </LayoutGroup>
  );
}
