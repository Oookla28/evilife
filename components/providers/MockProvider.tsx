"use client";

import { useEffect } from "react";

let mswStartPromise: Promise<void> | null = null;

/**
 * 仅在显式启用时启动 MSW；默认请求真实后端。
 * 始终同步渲染 children，避免 SSR 返回 null / 客户端返回内容造成 hydration 不一致。
 */
export function MockProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "development") return;
    if (process.env.NEXT_PUBLIC_USE_MOCKS !== "true") return;
    if (typeof window === "undefined") return;

    if (!mswStartPromise) {
      mswStartPromise = (async () => {
        const { worker } = await import("../../mocks/browser");
        await worker.start({
          onUnhandledRequest: "bypass",
          quiet: true,
        });
      })().catch((err) => {
        console.warn("[MockProvider] MSW failed to start:", err);
        mswStartPromise = null;
      });
    }
  }, []);

  return <>{children}</>;
}
