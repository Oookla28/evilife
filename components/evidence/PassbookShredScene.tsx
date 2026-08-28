"use client";

/**
 * iOS 6 Passbook 碎纸机重演（PKPassShredderSheet 语义）
 *
 * 原机状态：shredderUpOnBack → shredderShred → finished → offscreen
 * 观感：底部金属碎纸机升起 → 卡片被卷进齿口 → 齿口下同步吐出竖条 + 纸屑
 * 资源：/public/shredder/* 来自 iOS 6.1.4 PassKit.framework
 */

import { useMemo } from "react";
import { motion } from "framer-motion";

export const SHRED_TOTAL_MS = 1700;
const RISE_MS = 320;
const FEED_MS = 1250;
const FEED_DELAY_MS = 280;
const STRIPS = 14;
const CARD_W = 240;
const CARD_H = 170;

export interface ShredCardVisual {
  title: string;
  tag: string;
  body: string;
  color: string;
}

function prand(seed: number) {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

/** 卡片正面（碎纸专用，无翻转） */
function PassFace({ card }: { card: ShredCardVisual }) {
  return (
    <div
      style={{
        width: CARD_W,
        height: CARD_H,
        borderRadius: 14,
        background: card.color,
        boxShadow:
          "0 8px 28px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.14)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: 16,
        color: "#fff",
      }}
    >
      <span
        style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          padding: "2px 8px",
          borderRadius: 6,
          background: "rgba(255,255,255,.15)",
          width: "fit-content",
          opacity: 0.9,
        }}
      >
        {card.tag}
      </span>
      <div>
        <div style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.3 }}>
          {card.title}
        </div>
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            opacity: 0.65,
            lineHeight: 1.45,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {card.body}
        </div>
      </div>
      <div
        style={{
          borderTop: "1px solid rgba(255,255,255,.12)",
          paddingTop: 8,
          fontSize: 9,
          opacity: 0.4,
          fontFamily: "ui-monospace, monospace",
        }}
      >
        是非题 Evidence
      </div>
    </div>
  );
}

/** 金属碎纸机机身（ShredderMetal + MicroPerf 齿） */
function ShredderMachine({ width }: { width: number }) {
  return (
    <div style={{ width, position: "relative" }}>
      {/* 上缘锯齿 — 咬合口 */}
      <div
        style={{
          display: "flex",
          gap: 1,
          padding: "0 6px",
          height: 10,
          alignItems: "flex-end",
        }}
      >
        {Array.from({ length: 42 }).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: i % 2 === 0 ? 9 : 6,
              borderRadius: "1px 1px 0 0",
              background:
                i % 3 === 0
                  ? "linear-gradient(180deg,#3a3a3a,#0a0a0a)"
                  : "linear-gradient(180deg,#555,#151515)",
              boxShadow: "inset 0 1px 0 rgba(255,255,255,.12)",
            }}
          />
        ))}
      </div>

      {/* 金属壳体 — 优先用原机贴图 */}
      <div
        style={{
          height: 52,
          borderRadius: "4px 4px 10px 10px",
          backgroundImage: "url(/shredder/ShredderMetal.png)",
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundColor: "#3a3a3a",
          boxShadow:
            "0 10px 28px rgba(0,0,0,.65), inset 0 1px 0 rgba(255,255,255,.28), inset 0 -2px 6px rgba(0,0,0,.5)",
          border: "1px solid rgba(255,255,255,.08)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* MicroPerf 叠加 */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: "url(/shredder/ShredderMicroPerf.png)",
            backgroundSize: "48px 48px",
            opacity: 0.35,
            mixBlendMode: "multiply",
            pointerEvents: "none",
          }}
        />
        {/* 高光条 */}
        <div
          style={{
            position: "absolute",
            left: 10,
            right: 10,
            top: 8,
            height: 1,
            background:
              "linear-gradient(90deg,transparent,rgba(255,255,255,.45),transparent)",
          }}
        />
        {/* 进纸缝 */}
        <div
          style={{
            position: "absolute",
            left: 16,
            right: 16,
            top: 18,
            height: 5,
            borderRadius: 3,
            background: "linear-gradient(180deg,#000,#1a1a1a)",
            boxShadow: "inset 0 1px 3px rgba(0,0,0,.9)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 8,
            textAlign: "center",
            fontSize: 8,
            letterSpacing: "0.14em",
            color: "rgba(255,255,255,.28)",
            fontFamily: "ui-monospace, monospace",
            textTransform: "uppercase",
          }}
        >
          PKPass Shredder
        </div>
      </div>
    </div>
  );
}

/**
 * 完整碎纸场景
 * 父级需在 SHRED_TOTAL_MS 后卸载并删除数据
 */
export function PassbookShredScene({ card }: { card: ShredCardVisual }) {
  // 齿口在场景中的 Y（卡片可视区高度）
  const MOUTH_Y = 158;
  const machineW = CARD_W + 36;
  const stripW = (CARD_W - (STRIPS - 1) * 1.5) / STRIPS;

  const particles = useMemo(
    () => Array.from({ length: 36 }, (_, i) => i + 1),
    [],
  );

  return (
    <div
      style={{
        position: "relative",
        width: machineW,
        height: MOUTH_Y + 130,
        margin: "0 auto",
      }}
    >
      {/* ── 1) 卡片被卷入齿口：上方视口裁切，卡片向下喂入 ── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: (machineW - CARD_W) / 2,
          width: CARD_W,
          height: MOUTH_Y,
          overflow: "hidden",
          zIndex: 5,
          // 底部轻微羽化，模拟咬入
          maskImage:
            "linear-gradient(to bottom, #000 0%, #000 88%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to bottom, #000 0%, #000 88%, transparent 100%)",
        }}
      >
        <motion.div
          initial={{ y: 8, scaleY: 1 }}
          animate={{
            y: MOUTH_Y + 8,
            // 接近齿口时略作 mesh 压扁感
            scaleY: [1, 1, 0.92, 0.78],
          }}
          transition={{
            y: {
              duration: FEED_MS / 1000,
              delay: FEED_DELAY_MS / 1000,
              ease: [0.4, 0.0, 0.2, 1],
            },
            scaleY: {
              duration: FEED_MS / 1000,
              delay: FEED_DELAY_MS / 1000,
              ease: "linear",
              times: [0, 0.55, 0.8, 1],
            },
          }}
          style={{ transformOrigin: "50% 100%" }}
        >
          <PassFace card={card} />
        </motion.div>
      </div>

      {/* ── 2) 金属碎纸机：自下升起就位（shredderUpOnBack） ── */}
      <motion.div
        initial={{ y: 70, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{
          duration: RISE_MS / 1000,
          ease: [0.22, 1, 0.36, 1],
        }}
        style={{
          position: "absolute",
          top: MOUTH_Y - 8,
          left: 0,
          zIndex: 30,
        }}
      >
        <ShredderMachine width={machineW} />
      </motion.div>

      {/* ── 3) 齿口下方：竖条纸（边锯边吐，从缝里出来再落下） ── */}
      <div
        style={{
          position: "absolute",
          top: MOUTH_Y + 28,
          left: (machineW - CARD_W) / 2,
          width: CARD_W,
          height: 100,
          zIndex: 10,
          pointerEvents: "none",
          overflow: "visible",
        }}
      >
        {Array.from({ length: STRIPS }).map((_, i) => {
          const sway = (i % 2 === 0 ? 1 : -1) * (6 + prand(i + 2) * 14);
          // 卡片喂入过程中陆续从齿口吐出
          const delay =
            (FEED_DELAY_MS + 80 + (i / STRIPS) * (FEED_MS * 0.55)) / 1000;
          const fall = 0.75 + prand(i + 5) * 0.35;
          return (
            <motion.div
              key={i}
              style={{
                position: "absolute",
                left: i * (stripW + 1.5),
                top: 0,
                width: stripW,
                height: 72 + prand(i) * 28,
                borderRadius: "0 0 1px 1px",
                background: card.color,
                boxShadow:
                  "inset 0 0 0 0.5px rgba(0,0,0,.35), 0 2px 4px rgba(0,0,0,.25)",
                overflow: "hidden",
                transformOrigin: "50% 0%",
              }}
              initial={{ y: -18, opacity: 0, rotateZ: 0, scaleY: 0.3 }}
              animate={{
                y: [-18, 0, 20, 90 + prand(i) * 40],
                opacity: [0, 1, 1, 0],
                rotateZ: [0, sway * 0.15, sway * 0.55, sway],
                scaleY: [0.25, 1, 1, 0.85],
              }}
              transition={{
                duration: fall,
                delay,
                ease: [0.33, 0, 0.2, 1],
                times: [0, 0.12, 0.35, 1],
              }}
            >
              {/* 竖向微纹理 */}
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  backgroundImage:
                    "repeating-linear-gradient(90deg, transparent 0 1px, rgba(0,0,0,.14) 1px 2px)",
                  opacity: 0.7,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  inset: 1,
                  fontSize: 6,
                  lineHeight: 1.1,
                  color: "rgba(255,255,255,.4)",
                  fontFamily: "ui-monospace, monospace",
                  writingMode: "vertical-rl",
                  overflow: "hidden",
                  letterSpacing: 0.5,
                }}
              >
                {card.title}
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* ── 4) 纸屑粒子（CAEmitterLayer）从齿口喷出 ── */}
      {particles.map((seed) => {
        const size = 1.8 + prand(seed) * 3.5;
        const x0 = (machineW - CARD_W) / 2 + prand(seed + 1) * CARD_W;
        const delay =
          (FEED_DELAY_MS + prand(seed + 3) * FEED_MS * 0.85) / 1000;
        const life = 0.55 + prand(seed + 4) * 0.45;
        return (
          <motion.div
            key={seed}
            style={{
              position: "absolute",
              left: x0,
              top: MOUTH_Y + 22,
              width: size,
              height: size * (1.1 + prand(seed + 6) * 1.2),
              borderRadius: prand(seed + 7) > 0.5 ? 1 : 0.5,
              background: card.color,
              zIndex: 25,
              pointerEvents: "none",
              boxShadow: "0 0 1px rgba(0,0,0,.35)",
            }}
            initial={{ opacity: 0, y: 0, x: 0, rotate: 0 }}
            animate={{
              opacity: [0, 1, 0],
              y: [0, 24 + prand(seed + 8) * 30, 70 + prand(seed + 9) * 55],
              x: [
                0,
                (prand(seed + 10) - 0.5) * 36,
                (prand(seed + 11) - 0.5) * 80,
              ],
              rotate: prand(seed + 12) * 480 - 240,
            }}
            transition={{
              duration: life,
              delay,
              ease: "easeOut",
            }}
          />
        );
      })}
    </div>
  );
}
