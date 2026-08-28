"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarDays, MessageSquareText, Utensils } from "lucide-react";
import { useConversationHistory } from "@/lib/chat/use-conversation-history";
import { FastingTimer } from "@/components/lifestyle/FastingTimer";
import { getTodayRecords, type TodayRecords } from "@/lib/api/today";

export default function TodayPage() {
  const today = new Date().toDateString();
  const { conversations: history } = useConversationHistory();
  const conversations = history.filter(
    (conversation) => new Date(conversation.updatedAt).toDateString() === today
  );
  const questions = conversations.reduce(
    (count, conversation) =>
      count + conversation.messages.filter((message) => message.role === "user").length,
    0
  );
  const [records, setRecords] = useState<TodayRecords | null>(null);
  const [recordsUnavailable, setRecordsUnavailable] = useState(false);
  const dateKey = useMemo(() => new Date().toISOString().slice(0, 10), []);

  useEffect(() => {
    getTodayRecords(dateKey)
      .then((result) => {
        setRecords(result);
        setRecordsUnavailable(false);
      })
      .catch(() => setRecordsUnavailable(true));
  }, [dateKey]);

  const mealRange = records?.meals.reduce(
    (total, meal) => [
      total[0] + meal.estimated_total_calories[0],
      total[1] + meal.estimated_total_calories[1],
    ] as [number, number],
    [0, 0] as [number, number]
  );

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 md:px-8">
      <h1 className="text-2xl font-bold text-text-primary">今日记录</h1>
      <p className="mt-2 text-sm text-text-secondary">
        汇总问答和经你确认的客观生活记录；估算值不会自动变成医疗建议。
      </p>
      <div className="mt-7 grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-border-divider bg-white p-5">
          <CalendarDays size={20} className="mb-4 text-brand" />
          <p className="text-3xl font-semibold text-text-primary">{conversations.length}</p>
          <p className="mt-1 text-sm text-text-secondary">今日对话</p>
        </div>
        <div className="rounded-2xl border border-border-divider bg-white p-5">
          <MessageSquareText size={20} className="mb-4 text-brand" />
          <p className="text-3xl font-semibold text-text-primary">{questions}</p>
          <p className="mt-1 text-sm text-text-secondary">今日问题</p>
        </div>
        <div className="rounded-2xl border border-border-divider bg-white p-5">
          <Utensils size={20} className="mb-4 text-[#A8663E]" />
          <p className="text-3xl font-semibold text-text-primary">
            {recordsUnavailable ? "--" : records?.meals.length ?? 0}
          </p>
          <p className="mt-1 text-sm text-text-secondary">已确认餐食</p>
          {mealRange && mealRange[1] > 0 ? (
            <p className="mt-2 text-xs text-text-secondary">
              估算合计 {mealRange[0]}–{mealRange[1]} kcal
            </p>
          ) : null}
        </div>
      </div>
      <div className="mt-5">
        <FastingTimer />
      </div>
    </div>
  );
}
