"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  BookOpenCheck,
  CalendarDays,
  ChevronRight,
  CircleUserRound,
  FlaskConical,
  History,
  LogOut,
  Menu,
  MessageSquarePlus,
  Sparkles,
  X,
} from "lucide-react";
import { useAuth } from "@/components/providers/AuthProvider";
import { useExperienceMode } from "@/components/providers/ExperienceModeProvider";

const navItems = [
  { name: "智能问答", href: "/", icon: MessageSquarePlus },
  { name: "健康档案", href: "/profile", icon: Activity },
  { name: "今日记录", href: "/today", icon: CalendarDays },
  { name: "对话历史", href: "/history", icon: History },
  { name: "证据实验室", href: "/lab", icon: FlaskConical },
];

export function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { mode, setMode } = useExperienceMode();

  const switchMode = (next: "life" | "professional") => {
    setMode(next);
    setMobileOpen(false);
    if (pathname !== "/") router.push("/");
  };

  const startNewConversation = () => {
    setMobileOpen(false);
    if (pathname === "/") window.dispatchEvent(new Event("evilife:new-conversation"));
    else router.push("/");
  };

  const signOut = async () => {
    await logout();
    router.replace("/login");
  };

  const content = (
    <div className="sidebar-inner">
      <div className="sidebar-brand">
        <span className="brand-mark"><Image src="/evilife-team-logo.jpg" alt="AIdearπ队" width={36} height={36} /></span>
        <div><strong>EviLife</strong><span>循证健康智能平台</span></div>
      </div>

      <div className="mode-switch" aria-label="切换使用模式">
        <button type="button" aria-pressed={mode === "life"} onClick={() => switchMode("life")}>
          <Sparkles size={15} /><span>生活版</span>
        </button>
        <button type="button" aria-pressed={mode === "professional"} onClick={() => switchMode("professional")}>
          <BookOpenCheck size={15} /><span>专业版</span>
        </button>
      </div>
      <p className="mode-caption">
        {mode === "life" ? "把医学证据讲成人能听懂的话" : "面向研究问题的深度证据检索"}
      </p>

      <button type="button" className="new-chat-button" onClick={startNewConversation}>
        <MessageSquarePlus size={17} /><span>发起新问题</span><ChevronRight size={15} />
      </button>

      <nav className="sidebar-nav">
        <p>工作台</p>
        {navItems.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link key={item.href} href={item.href} onClick={() => setMobileOpen(false)} data-active={active}>
              <Icon size={17} /><span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-status">
        <span className="status-dot" />
        <div><strong>Evidence Engine</strong><span>本地证据库与实时检索已就绪</span></div>
      </div>

      <div className="sidebar-account">
        <span className="account-avatar"><CircleUserRound size={20} /></span>
        <div><strong>{user?.display_name}</strong><span>{user?.email}</span></div>
        <button type="button" onClick={() => void signOut()} aria-label="退出登录"><LogOut size={17} /></button>
      </div>
    </div>
  );

  return (
    <>
      <aside className="sidebar-desktop">{content}</aside>
      <header className="mobile-header">
        <div className="brand-lockup"><span className="brand-mark"><Image src="/evilife-team-logo.jpg" alt="AIdearπ队" width={34} height={34} /></span><strong>EviLife</strong></div>
        <button type="button" onClick={() => setMobileOpen(true)} aria-label="打开导航"><Menu size={21} /></button>
      </header>
      {mobileOpen ? (
        <div className="mobile-drawer" role="dialog" aria-modal="true">
          <button type="button" className="drawer-backdrop" onClick={() => setMobileOpen(false)} aria-label="关闭导航" />
          <aside>
            <button type="button" className="drawer-close" onClick={() => setMobileOpen(false)} aria-label="关闭导航"><X size={20} /></button>
            {content}
          </aside>
        </div>
      ) : null}
    </>
  );
}
