export type CoverFlowStep = -1 | 0 | 1;

/**
 * Convert a horizontal drag into one deterministic CoverFlow step.
 * A quick flick can cross the threshold with less travel, while slow taps and
 * small accidental movements always snap back to the current card.
 */
export function resolveCoverFlowSwipe(
  offsetX: number,
  velocityX: number,
  threshold = 46
): CoverFlowStep {
  const projectedDistance = offsetX + velocityX * 0.12;
  if (projectedDistance <= -threshold) return 1;
  if (projectedDistance >= threshold) return -1;
  return 0;
}

export function clampCoverFlowIndex(index: number, count: number) {
  return Math.max(0, Math.min(Math.max(0, count - 1), index));
}
