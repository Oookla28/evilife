import type { Metadata } from "next";
import "./globals.css";
import { MainLayout } from "@/components/layout/MainLayout";
import { MockProvider } from "@/components/providers/MockProvider";
import { FontApplier } from "@/components/providers/FontApplier";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { ExperienceModeProvider } from "@/components/providers/ExperienceModeProvider";

export const metadata: Metadata = {
  title: "EviLife - 双模式循证健康智能平台",
  description: "连接个人健康数据与医学文献证据的双模式智能平台。",
  icons: { icon: "/evilife-team-logo.jpg", apple: "/evilife-team-logo.jpg" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className="h-full antialiased"
      suppressHydrationWarning
    >
      <body
        className="min-h-full flex flex-col font-sans bg-bg-page text-text-primary"
        suppressHydrationWarning
      >
        <MockProvider>
          <FontApplier />
          <AuthProvider>
            <ExperienceModeProvider>
              <MainLayout>{children}</MainLayout>
            </ExperienceModeProvider>
          </AuthProvider>
        </MockProvider>
      </body>
    </html>
  );
}
