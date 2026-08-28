"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import Image from "next/image";
import { useAuth } from "@/components/providers/AuthProvider";
import { Sidebar } from "./Sidebar";

export function MainLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const isLogin = pathname === "/login";
  const isAdmin = pathname.startsWith("/admin");

  useEffect(() => {
    if (!loading && !user && !isLogin) router.replace("/login");
  }, [isLogin, loading, router, user]);

  if (isLogin) return <>{children}</>;

  if (loading || !user) {
    return (
      <div className="app-loading">
        <span className="brand-mark"><Image src="/evilife-team-logo.jpg" alt="AIdearπ队" width={40} height={40} /></span>
        <p>正在安全读取你的EviLife档案…</p>
      </div>
    );
  }

  if (isAdmin) return <div className="min-h-screen bg-bg-page">{children}</div>;

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">{children}</main>
    </div>
  );
}
