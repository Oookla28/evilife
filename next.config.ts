import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  // Netlify 静态部署：NEXT_STATIC_EXPORT=1 时导出纯静态站点（演示模式用）
  ...(process.env.NEXT_STATIC_EXPORT === "1"
    ? {
        output: "export" as const,
        images: { unoptimized: true },
      }
    : {}),
  async rewrites() {
    const backendOrigin = (process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000").replace(/\/$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendOrigin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
