"use client";

import { useState, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ExternalLink, ChevronLeft, ChevronRight, FileText } from "lucide-react";

export interface EvidenceCard {
  id: string;
  title: string;
  source: string;
  year: number;
  type: string;
  tag: "support" | "boundary" | "neutral";
  
  // Details
  study_population?: string;
  main_findings?: string;
  support_scope?: string;
  prohibit_derivation?: string;
  limitations?: string;
  url?: string;
}

export interface EvidenceFlowProps {
  cards: EvidenceCard[];
}

export function EvidenceFlow({ cards }: EvidenceFlowProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const prefersReducedMotion = useReducedMotion();
  const scrollRef = useRef<HTMLDivElement>(null);

  // If reduced motion or likely mobile (we can use CSS media queries for layout, but for Framer, let's rely on prefersReducedMotion and CSS for mobile fallback)
  // For simplicity, we'll build a CSS snap-scroll container for mobile/reduced motion,
  // and a JS-driven 3D carousel for desktop with motion allowed.

  const is3DEnabled = !prefersReducedMotion;

  const handleNext = () => {
    if (currentIndex < cards.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setExpandedId(null);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(prev => prev - 1);
      setExpandedId(null);
    }
  };

  const toggleExpand = (id: string, index: number) => {
    if (index !== currentIndex && is3DEnabled) {
      setCurrentIndex(index);
      setExpandedId(null);
      return;
    }
    setExpandedId(prev => prev === id ? null : id);
  };

  const getTagColor = (tag: string) => {
    if (tag === "support") return "bg-evidence-support text-white";
    if (tag === "boundary") return "bg-evidence-boundary text-white";
    return "bg-text-secondary text-white";
  };

  const getTagLabel = (tag: string) => {
    if (tag === "support") return "支持";
    if (tag === "boundary") return "边界条件";
    return "中立";
  };

  // Fallback layout for mobile or reduced motion
  if (!is3DEnabled) {
    return (
      <div className="w-full relative">
        <div 
          ref={scrollRef}
          className="flex overflow-x-auto snap-x snap-mandatory gap-4 pb-4 hide-scrollbar"
          style={{ scrollBehavior: 'smooth' }}
        >
          {cards.map((card, i) => (
            <div 
              key={card.id} 
              className="min-w-[280px] w-[85%] sm:w-[320px] flex-shrink-0 snap-center bg-white border border-border-divider rounded-2xl shadow-sm overflow-hidden flex flex-col"
            >
              <div className="p-4 border-b border-border-divider bg-bg-page/50 cursor-pointer" onClick={() => toggleExpand(card.id, i)}>
                <div className="flex justify-between items-start mb-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getTagColor(card.tag)}`}>
                    {getTagLabel(card.tag)}
                  </span>
                  <span className="text-xs text-text-secondary font-mono">{card.year}</span>
                </div>
                <h3 className="font-semibold text-text-primary text-sm leading-tight line-clamp-2 mb-1">{card.title}</h3>
                <div className="text-xs text-text-secondary truncate">{card.source} • {card.type}</div>
              </div>
              
              {expandedId === card.id && (
                <div className="p-4 flex flex-col gap-3 text-sm animate-in slide-in-from-top-2">
                  {card.main_findings && (
                    <div><span className="font-medium text-text-primary">主要发现：</span> <span className="text-text-secondary">{card.main_findings}</span></div>
                  )}
                  {card.study_population && (
                    <div><span className="font-medium text-text-primary">研究人群：</span> <span className="text-text-secondary">{card.study_population}</span></div>
                  )}
                  {card.support_scope && (
                    <div className="text-evidence-support"><span className="font-medium">支持范围：</span> {card.support_scope}</div>
                  )}
                  {card.prohibit_derivation && (
                    <div className="text-risk-refused"><span className="font-medium">禁止推导：</span> {card.prohibit_derivation}</div>
                  )}
                  {card.limitations && (
                    <div><span className="font-medium text-text-primary">局限：</span> <span className="text-text-secondary">{card.limitations}</span></div>
                  )}
                  {card.url && (
                    <a href={card.url} target="_blank" rel="noreferrer" className="mt-2 text-brand hover:underline flex items-center gap-1 text-xs">
                      <ExternalLink size={12} /> 原始链接
                    </a>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Desktop 3D Cover Flow
  return (
    <div className="relative w-full h-[400px] flex items-center justify-center overflow-hidden perspective-1000 hidden md:flex">
      <button 
        onClick={handlePrev}
        disabled={currentIndex === 0}
        className="absolute left-2 z-20 p-2 rounded-full bg-white border border-border-divider shadow-sm disabled:opacity-30 hover:bg-black/5"
      >
        <ChevronLeft size={24} className="text-text-primary" />
      </button>

      <div className="relative w-full max-w-[400px] h-full flex items-center justify-center preserve-3d">
        {cards.map((card, index) => {
          const offset = index - currentIndex;
          const isCenter = offset === 0;
          const isVisible = Math.abs(offset) <= 2;
          
          if (!isVisible) return null;

          // Calculate 3D transforms
          const rotateY = offset * -25;
          const translateZ = Math.abs(offset) * -100;
          const translateX = offset * 60;
          const zIndex = 10 - Math.abs(offset);
          const opacity = 1 - Math.abs(offset) * 0.3;

          return (
            <motion.div
              key={card.id}
              initial={false}
              animate={{
                rotateY: isCenter && expandedId === card.id ? 0 : rotateY,
                z: isCenter && expandedId === card.id ? 50 : translateZ,
                x: `${translateX}%`,
                opacity: opacity,
              }}
              transition={{ type: "spring", stiffness: 260, damping: 20 }}
              style={{
                position: "absolute",
                width: "320px",
                zIndex: isCenter && expandedId === card.id ? 20 : zIndex,
                transformStyle: "preserve-3d",
              }}
              className="bg-white border border-border-divider rounded-2xl shadow-lg cursor-pointer"
              onClick={() => toggleExpand(card.id, index)}
            >
              <div className="p-5 border-b border-border-divider bg-bg-page/50 rounded-t-2xl">
                <div className="flex justify-between items-start mb-3">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getTagColor(card.tag)}`}>
                    {getTagLabel(card.tag)}
                  </span>
                  <span className="text-xs text-text-secondary font-mono">{card.year}</span>
                </div>
                <h3 className="font-semibold text-text-primary text-base leading-tight mb-2 line-clamp-3">{card.title}</h3>
                <div className="text-xs text-text-secondary flex items-center gap-1">
                  <FileText size={12} />
                  <span className="truncate">{card.source}</span>
                  <span>•</span>
                  <span>{card.type}</span>
                </div>
              </div>

              <div className="p-5 h-[200px] overflow-y-auto hide-scrollbar bg-white rounded-b-2xl">
                {(isCenter && expandedId === card.id) ? (
                  <div className="flex flex-col gap-4 text-sm animate-in fade-in">
                    {card.main_findings && (
                      <div><span className="font-medium text-text-primary block mb-1">主要发现：</span> <span className="text-text-secondary">{card.main_findings}</span></div>
                    )}
                    {card.study_population && (
                      <div><span className="font-medium text-text-primary">研究人群：</span> <span className="text-text-secondary">{card.study_population}</span></div>
                    )}
                    {card.support_scope && (
                      <div className="text-evidence-support"><span className="font-medium block mb-1">支持范围：</span> {card.support_scope}</div>
                    )}
                    {card.prohibit_derivation && (
                      <div className="text-risk-refused"><span className="font-medium block mb-1">禁止推导：</span> {card.prohibit_derivation}</div>
                    )}
                    {card.limitations && (
                      <div><span className="font-medium text-text-primary block mb-1">局限：</span> <span className="text-text-secondary">{card.limitations}</span></div>
                    )}
                    {card.url && (
                      <a href={card.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex text-brand hover:underline items-center gap-1 text-xs">
                        <ExternalLink size={12} /> 原始链接
                      </a>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-text-secondary line-clamp-6 opacity-60">
                    {card.main_findings || "点击查看详情..."}
                  </div>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>

      <button 
        onClick={handleNext}
        disabled={currentIndex === cards.length - 1}
        className="absolute right-2 z-20 p-2 rounded-full bg-white border border-border-divider shadow-sm disabled:opacity-30 hover:bg-black/5"
      >
        <ChevronRight size={24} className="text-text-primary" />
      </button>
    </div>
  );
}
