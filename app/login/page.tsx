"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { ArrowRight, BookOpenCheck, LockKeyhole, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/providers/AuthProvider";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login, register } = useAuth();
  const [creating, setCreating] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, router, user]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      if (creating) {
        await register({ email, password, display_name: displayName });
      } else {
        await login({ email, password });
      }
      router.replace("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "暂时无法登录，请稍后重试。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-story">
        <div className="brand-lockup brand-lockup-light">
          <span className="brand-mark"><Image src="/evilife-team-logo.jpg" alt="AIdearπ队" width={38} height={38} /></span>
          <span>EviLife</span>
        </div>
        <div className="auth-story-copy">
          <p className="eyebrow eyebrow-light">EVIDENCE-GROUNDED HEALTH INTELLIGENCE</p>
          <h1>让每一次健康判断，<br />都能回到证据本身。</h1>
          <p>生活版理解你的长期数据，专业版拆解研究与文献；两种视角，共享同一条可信证据链。</p>
        </div>
        <div className="auth-capabilities">
          <div><ShieldCheck size={18} /><span>医学结论受证据与安全规则约束</span></div>
          <div><BookOpenCheck size={18} /><span>支持与反对证据同步呈现</span></div>
          <div><LockKeyhole size={18} /><span>账号数据保存在服务端运行库</span></div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <p className="eyebrow">WELCOME TO EVILIFE</p>
          <h2>{creating ? "创建你的健康档案" : "继续你的证据旅程"}</h2>
          <p className="auth-intro">
            {creating ? "注册后，你的问答历史与健康记录会跨设备保存。" : "登录后继续查看此前的健康数据、分析与文献记录。"}
          </p>
          <form onSubmit={submit} className="auth-form">
            {creating ? (
              <label>称呼<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" placeholder="例如：小林" required /></label>
            ) : null}
            <label>邮箱<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" placeholder="name@example.com" required /></label>
            <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={creating ? "new-password" : "current-password"} placeholder={creating ? "至少10位，包含字母和数字" : "输入你的密码"} minLength={creating ? 10 : 1} required /></label>
            {error ? <p role="alert" className="auth-error">{error}</p> : null}
            <button type="submit" disabled={submitting} className="auth-submit">
              <span>{submitting ? "正在处理…" : creating ? "创建账号" : "安全登录"}</span><ArrowRight size={18} />
            </button>
          </form>
          <button type="button" className="auth-switch" onClick={() => { setCreating((value) => !value); setError(""); }}>
            {creating ? "已有账号？返回登录" : "第一次使用？创建账号"}
          </button>
          <p className="auth-boundary">EviLife用于健康信息整理与循证支持，不替代医生诊断或治疗。</p>
        </div>
      </section>
    </main>
  );
}
