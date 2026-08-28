"use client";

import { useCallback, useEffect, useRef, type KeyboardEvent, type WheelEvent } from "react";
import type { PanInfo } from "framer-motion";
import { clampCoverFlowIndex, resolveCoverFlowSwipe } from "./cover-flow-gesture";

interface CoverFlowControlsOptions {
  index: number;
  count: number;
  enabled?: boolean;
  onIndexChange: (index: number) => void;
}

export function useCoverFlowControls({
  index,
  count,
  enabled = true,
  onIndexChange,
}: CoverFlowControlsOptions) {
  const wheelDistanceRef = useRef(0);
  const wheelResetRef = useRef<number | null>(null);
  const lastWheelMoveRef = useRef(0);

  const move = useCallback(
    (step: -1 | 1) => {
      if (!enabled || count < 2) return;
      const next = clampCoverFlowIndex(index + step, count);
      if (next !== index) onIndexChange(next);
    },
    [count, enabled, index, onIndexChange]
  );

  const onDragEnd = useCallback(
    (info: PanInfo) => {
      const step = resolveCoverFlowSwipe(info.offset.x, info.velocity.x);
      if (step) move(step);
    },
    [move]
  );

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        move(-1);
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        move(1);
      }
    },
    [move]
  );

  const onWheel = useCallback(
    (event: WheelEvent<HTMLElement>) => {
      if (!enabled || count < 2) return;
      const horizontal = event.deltaX;
      if (Math.abs(horizontal) < 3 || Math.abs(horizontal) <= Math.abs(event.deltaY)) return;

      event.preventDefault();
      wheelDistanceRef.current += horizontal;
      const now = performance.now();
      if (Math.abs(wheelDistanceRef.current) >= 34 && now - lastWheelMoveRef.current > 260) {
        move(wheelDistanceRef.current > 0 ? 1 : -1);
        wheelDistanceRef.current = 0;
        lastWheelMoveRef.current = now;
      }

      if (wheelResetRef.current !== null) window.clearTimeout(wheelResetRef.current);
      wheelResetRef.current = window.setTimeout(() => {
        wheelDistanceRef.current = 0;
      }, 180);
    },
    [count, enabled, move]
  );

  useEffect(
    () => () => {
      if (wheelResetRef.current !== null) window.clearTimeout(wheelResetRef.current);
    },
    []
  );

  return { move, onDragEnd, onKeyDown, onWheel };
}
