"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock3, MessageSquare, Search, Trash2 } from "lucide-react";
import { deleteConversation } from "@/lib/chat/history-store";
import { useConversationHistory } from "@/lib/chat/use-conversation-history";

export function HistoryList({ searchable = false }: { searchable?: boolean }) {
  const router = useRouter();
  const { conversations, loading, error } = useConversationHistory();
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return normalized
      ? conversations.filter((conversation) =>
          conversation.title.toLowerCase().includes(normalized)
        )
      : conversations;
  }, [conversations, query]);

  const openConversation = (sessionId: string) => {
    const conversation = conversations.find((item) => item.sessionId === sessionId);
    if (!conversation) return;
    sessionStorage.setItem("evilife_restore_conversation", JSON.stringify(conversation));
    router.push("/");
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 md:px-8">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-text-primary">
          {searchable ? "搜索历史" : "最近对话"}
        </h1>
        <p className="mt-2 text-sm text-text-secondary">
          对话已与当前账号同步，换设备登录后仍可继续。
        </p>
      </div>

      {searchable ? (
        <label className="mb-6 flex items-center gap-3 rounded-2xl border border-border-divider bg-white px-4 py-3 shadow-sm">
          <Search size={18} className="text-text-secondary" />
          <span className="sr-only">搜索对话</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索问题关键词"
            className="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-secondary/60"
          />
        </label>
      ) : null}

      {filtered.length ? (
        <ul className="divide-y divide-border-divider overflow-hidden rounded-2xl border border-border-divider bg-white">
          {filtered.map((conversation) => (
            <li key={conversation.sessionId} className="group flex items-center gap-2 p-2">
              <button
                type="button"
                onClick={() => openConversation(conversation.sessionId)}
                className="flex min-w-0 flex-1 items-start gap-3 rounded-xl p-3 text-left hover:bg-bg-page"
              >
                <MessageSquare size={18} className="mt-0.5 shrink-0 text-brand" />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-text-primary">
                    {conversation.title}
                  </span>
                  <span className="mt-1 flex items-center gap-1 text-xs text-text-secondary">
                    <Clock3 size={12} />
                    {new Date(conversation.updatedAt).toLocaleString("zh-CN", {
                      month: "numeric",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </span>
              </button>
              <button
                type="button"
                onClick={() => void deleteConversation(conversation.sessionId)}
                aria-label={`删除对话：${conversation.title}`}
                className="rounded-lg p-2 text-text-secondary opacity-100 hover:bg-risk-refused/5 hover:text-risk-refused md:opacity-0 md:group-hover:opacity-100"
              >
                <Trash2 size={16} />
              </button>
            </li>
          ))}
        </ul>
      ) : loading ? (
        <div className="rounded-2xl border border-border-divider bg-white p-12 text-center text-sm text-text-secondary">
          正在从账号数据库加载历史记录…
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border-divider p-12 text-center">
          <MessageSquare className="mx-auto mb-3 text-text-secondary/50" size={28} />
          <p className="text-sm text-text-secondary">
            {error || (query ? "没有找到匹配的对话。" : "还没有账号对话记录。")}
          </p>
        </div>
      )}
    </div>
  );
}
