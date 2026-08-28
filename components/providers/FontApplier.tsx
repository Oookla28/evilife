"use client";

import { useEffect } from "react";
import { initCustomFont } from "@/lib/fonts";

/**
 * Applies a previously saved custom font on mount so the setting survives
 * page reloads. Renders nothing.
 */
export function FontApplier() {
  useEffect(() => {
    initCustomFont();
  }, []);
  return null;
}
