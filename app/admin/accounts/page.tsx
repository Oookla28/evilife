"use client";

import { useEffect, useState } from "react";
import { Activity, ArrowLeft, CalendarDays, KeyRound, LogOut, Mail, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAccountSummary, type AccountSummary } from "@/lib/api/auth";
import { useAuth } from "@/components/providers/AuthProvider";

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" }) : "暂无记录";
}

export default function AdminAccountsPage() {
  const router = useRouter();
  const { logout } = useAuth();
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [error, setError] = useState("");
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    getAccountSummary().then(setSummary).catch((cause) => setError(cause instanceof Error ? cause.message : "账号数据加载失败"));
  }, []);

  const signOut = async () => {
    setSigningOut(true);
    await logout();
    router.replace("/login");
  };

  return <main className="min-h-screen bg-[#F4F7F6]"><header className="border-b border-border-divider bg-white"><div className="mx-auto flex max-w-[1180px] items-center justify-between px-5 py-4 sm:px-8"><div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-white"><Activity size={18} /></div><div><p className="text-sm font-semibold text-text-primary">EviLife Admin</p><p className="text-[11px] text-text-secondary">账号与运行状态管理</p></div></div><div className="flex items-center gap-3"><Link href="/" className="inline-flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary"><ArrowLeft size={14} />返回应用</Link><button type="button" onClick={() => void signOut()} disabled={signingOut} className="inline-flex items-center gap-1.5 rounded-lg border border-border-divider px-3 py-2 text-xs font-medium text-text-secondary hover:bg-bg-page disabled:opacity-60"><LogOut size={14} />{signingOut ? "退出中" : "退出"}</button></div></div></header><div className="mx-auto max-w-[1180px] px-5 py-8 sm:px-8"><div className="mb-6"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand">ACCOUNT MANAGEMENT</p><h1 className="mt-2 text-2xl font-semibold text-text-primary">账号管理后台</h1><p className="mt-2 text-sm text-text-secondary">查看运行库账号概况与当前登录身份。</p></div>{error ? <p role="alert" className="mb-4 rounded-xl bg-risk-refused/5 px-4 py-3 text-sm text-risk-refused">{error}</p> : null}{summary ? <div className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]"><section className="rounded-2xl border border-border-divider bg-white p-6"><div className="flex items-center gap-4"><div className="grid h-14 w-14 place-items-center rounded-2xl bg-brand/10 text-brand"><UserRound size={26} /></div><div><h2 className="text-lg font-semibold text-text-primary">{summary.user.display_name}</h2><p className="mt-1 flex items-center gap-1.5 text-sm text-text-secondary"><Mail size={14} />{summary.user.email}</p></div><span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-brand/10 px-3 py-1.5 text-xs font-medium text-brand"><ShieldCheck size={14} />当前会话</span></div><div className="mt-7 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-bg-page p-4"><p className="flex items-center gap-1.5 text-xs text-text-secondary"><CalendarDays size={14} />注册时间</p><p className="mt-2 text-sm font-medium text-text-primary">{formatDate(summary.registered_at)}</p></div><div className="rounded-xl bg-bg-page p-4"><p className="flex items-center gap-1.5 text-xs text-text-secondary"><KeyRound size={14} />最近登录</p><p className="mt-2 text-sm font-medium text-text-primary">{formatDate(summary.last_login_at)}</p></div></div></section><section className="rounded-2xl border border-border-divider bg-white p-6"><p className="text-xs text-text-secondary">运行库注册账号</p><p className="mt-2 text-4xl font-semibold text-text-primary">{summary.total_accounts}</p><p className="mt-3 text-xs leading-5 text-text-secondary">统计来自当前 FastAPI 运行库。密码哈希、会话令牌和健康数据不会在后台页面展示。</p></section></div> : <div className="rounded-2xl border border-border-divider bg-white p-8 text-sm text-text-secondary">正在读取账号数据…</div>}</div></main>;
}
