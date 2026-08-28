"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, Copy, FileText, ImageIcon, RotateCcw } from "lucide-react";
import { Composer, type ComposerState } from "@/components/composer/Composer";
import { RunStatus } from "@/components/chat/RunStatus";
import { MascotSlot, type MascotState } from "@/components/mascot/MascotSlot";
import { ModuleRenderer } from "@/components/modules/ModuleRenderer";
import { adaptModulePlan } from "@/lib/api/adapters";
import { StreamClient } from "@/lib/api/events";
import { orchestrate } from "@/lib/api/orchestrate";
import type { GateStatus, ModulePlanItem, OrchestrateResponse } from "@/lib/api/types";
import {
  createSessionId,
  saveConversation,
  type StoredMessage,
} from "@/lib/chat/history-store";
import {
  initialRunState,
  reduceRunState,
  type RunState,
} from "@/lib/chat/run-state";
import { getAttachmentKind } from "@/lib/attachments";
import { useExperienceMode } from "@/components/providers/ExperienceModeProvider";

export interface MessageItem extends StoredMessage {
  runState?: RunState;
  gateStatus?: GateStatus;
}

const lifeSuggestions = [
  "鸡蛋一天吃几个更合适？先给我一句话答案",
  "咖啡到底健康不健康？请用大白话解释",
  "16:8 真的能减肥吗？",
  "我的体检指标有点异常，该先关注什么？",
];

const professionalSuggestions = [
  "地中海饮食对心血管风险有什么证据？",
  "限钠饮食对高血压是否真的有帮助？",
  "16:8 一定能减肥吗？",
  "拍照估算热量到底准不准？",
];

const createId = (prefix: string) => `${prefix}-${createSessionId()}`;

const isCrisisMessage = (message: MessageItem) =>
  message.modulePlan?.some((item) =>
    item.type === "CrisisSupportCard" || item.type === "ExtremeCrisisCareCard"
  ) ?? false;

const mascotStateForMessage = (message: MessageItem): MascotState => {
  if (isCrisisMessage(message)) return "care";
  if (message.gateStatus === "refused") return "refuse";

  switch (message.runState?.phase) {
    case "starting":
    case "routing":
    case "collecting":
    case "streaming":
      return "thinking";
    case "ready":
      return "success";
    case "failed":
      return "failure";
    case "stopped":
      return "refuse";
    default:
      return "idle";
  }
};

export default function Home() {
  const { mode } = useExperienceMode();
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [sessionId, setSessionId] = useState(() => createSessionId());
  const [composerState, setComposerState] = useState<ComposerState>("default");
  const [errorMessage, setErrorMessage] = useState("");
  const [showJumpToBottom, setShowJumpToBottom] = useState(false);
  const streamClientRef = useRef<StreamClient | null>(null);
  const requestAbortRef = useRef<AbortController | null>(null);
  const activeAssistantIdRef = useRef<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const followLatestRef = useRef(true);
  const hasStarted = messages.length > 0;

  const resetConversation = useCallback(() => {
    streamClientRef.current?.disconnect();
    requestAbortRef.current?.abort();
    requestAbortRef.current = null;
    streamClientRef.current = null;
    activeAssistantIdRef.current = null;
    setMessages([]);
    setSessionId(createSessionId());
    setComposerState("default");
    setErrorMessage("");
    setShowJumpToBottom(false);
    followLatestRef.current = true;
  }, []);

  useEffect(() => {
    const restoreRaw = sessionStorage.getItem("evilife_restore_conversation");
    if (restoreRaw) {
      try {
        const restored = JSON.parse(restoreRaw) as {
          sessionId: string;
          messages: StoredMessage[];
        };
        queueMicrotask(() => {
          setSessionId(restored.sessionId);
          setMessages(restored.messages);
        });
      } catch {
        // Ignore a stale local history entry and start a clean conversation.
      }
      sessionStorage.removeItem("evilife_restore_conversation");
    }
    window.addEventListener("evilife:new-conversation", resetConversation);
    return () => window.removeEventListener("evilife:new-conversation", resetConversation);
  }, [resetConversation]);

  useEffect(() => {
    if (!messages.length) return;
    const firstQuestion = messages.find(
      (message) => message.role === "user" && message.content
    )?.content;
    void saveConversation({
      sessionId,
      title: firstQuestion?.slice(0, 42) || "附件对话",
      mode,
      updatedAt: new Date().toISOString(),
      messages: messages.map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        file: message.file,
        modulePlan: message.modulePlan,
      })),
    });
  }, [messages, mode, sessionId]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || !followLatestRef.current) return;
    const frame = requestAnimationFrame(() => {
      const latestAssistant = [...messages]
        .reverse()
        .find((message) => message.role === "assistant");
      if (latestAssistant && isCrisisMessage(latestAssistant)) {
        const target = document.getElementById(`message-${latestAssistant.id}`);
        if (target) {
          const top =
            target.getBoundingClientRect().top -
            container.getBoundingClientRect().top +
            container.scrollTop -
            16;
          container.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
          followLatestRef.current = false;
          return;
        }
      }
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    });
    return () => cancelAnimationFrame(frame);
  }, [messages]);

  useEffect(
    () => () => {
      streamClientRef.current?.disconnect();
      requestAbortRef.current?.abort();
    },
    []
  );

  const updateAssistant = useCallback(
    (assistantId: string, update: (message: MessageItem) => MessageItem) => {
      setMessages((previous) =>
        previous.map((message) =>
          message.id === assistantId ? update(message) : message
        )
      );
    },
    []
  );

  const startStream = useCallback(
    (result: OrchestrateResponse, assistantId: string) => {
      const client = new StreamClient(result.run_id);
      streamClientRef.current = client;
      setComposerState("streaming");

      client.connect(
        (event) => {
          updateAssistant(assistantId, (message) => ({
            ...message,
            runState: reduceRunState(message.runState ?? initialRunState, event),
            modulePlan: event.payload?.module_plan
              ? adaptModulePlan(
                  event.payload.module_plan as ModulePlanItem[],
                  result
                )
              : message.modulePlan,
          }));
        },
        () => {
          updateAssistant(assistantId, (message) => ({
            ...message,
            runState: {
              ...(message.runState ?? initialRunState),
              phase: "failed",
              error: "连接中断，已自动重试一次。",
            },
          }));
          setComposerState("error");
          setErrorMessage("连接异常中断，可重新生成回答。");
          activeAssistantIdRef.current = null;
        },
        () => {
          setComposerState("default");
          setErrorMessage("");
          streamClientRef.current = null;
          activeAssistantIdRef.current = null;
        }
      );
    },
    [updateAssistant]
  );

  const handleSend = useCallback(
    async (text: string, file: File | null) => {
      const attachmentKind = file ? getAttachmentKind(file) : null;
      followLatestRef.current = true;
      setShowJumpToBottom(false);
      streamClientRef.current?.disconnect();
      requestAbortRef.current?.abort();
      const requestController = new AbortController();
      requestAbortRef.current = requestController;
      const assistantId = createId("assistant");
      activeAssistantIdRef.current = assistantId;

      const userMessage: MessageItem = {
        id: createId("user"),
        role: "user",
        content: text.trim() || undefined,
        file: file
          ? {
              name: file.name,
              type:
                file.type ||
                (attachmentKind === "image"
                  ? "image/unknown"
                  : "application/octet-stream"),
            }
          : undefined,
      };
      const assistantMessage: MessageItem = {
        id: assistantId,
        role: "assistant",
        runState: { ...initialRunState, phase: "starting" },
        modulePlan: [
          {
            module_id: createId("loading"),
            type: "LoadingModule",
            status: "loading",
            props: { message: "咱们先把问题捋一遍，再去一条条核对证据…" },
          },
        ],
      };

      setMessages((previous) => [...previous, userMessage, assistantMessage]);
      setComposerState("sending");
      setErrorMessage("");

      try {
        const result = await orchestrate({
          text: text.trim() || undefined,
          image: attachmentKind === "image" ? file ?? undefined : undefined,
          document: attachmentKind === "document" ? file ?? undefined : undefined,
          session_id: sessionId,
          mode: mode === "professional" ? "evaluation" : "auto",
          signal: requestController.signal,
        });
        if (requestController.signal.aborted) return;
        requestAbortRef.current = null;
        updateAssistant(assistantId, (message) => ({
          ...message,
          gateStatus: result.gate_status,
          modulePlan: adaptModulePlan(result.module_plan, result),
        }));
        startStream(result, assistantId);
      } catch (error) {
        if (requestController.signal.aborted) return;
        requestAbortRef.current = null;
        const message = error instanceof Error ? error.message : "请求失败，请稍后重试";
        updateAssistant(assistantId, (item) => ({
          ...item,
          modulePlan: [],
          runState: { phase: "failed", streamedText: "", error: message },
        }));
        setComposerState("error");
        setErrorMessage(message);
        activeAssistantIdRef.current = null;
      }
    },
    [mode, sessionId, startStream, updateAssistant]
  );

  const handleStop = useCallback(() => {
    streamClientRef.current?.disconnect();
    requestAbortRef.current?.abort();
    requestAbortRef.current = null;
    streamClientRef.current = null;
    const assistantId = activeAssistantIdRef.current;
    if (assistantId) {
      updateAssistant(assistantId, (message) => ({
        ...message,
        runState: {
          ...(message.runState ?? initialRunState),
          phase: "stopped",
        },
      }));
    }
    activeAssistantIdRef.current = null;
    setComposerState("default");
  }, [updateAssistant]);

  const retryAt = useCallback(
    (assistantIndex: number) => {
      const previousUser = [...messages.slice(0, assistantIndex)]
        .reverse()
        .find((message) => message.role === "user");
      if (previousUser?.content) void handleSend(previousUser.content, null);
    },
    [handleSend, messages]
  );

  const handleConversationScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const isNearBottom = distanceFromBottom < 96;
    followLatestRef.current = isNearBottom;
    setShowJumpToBottom(!isNearBottom);
  }, []);

  const jumpToBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    followLatestRef.current = true;
    setShowJumpToBottom(false);
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, []);

  return (
    <div className="relative flex h-full flex-col">
      <div
        ref={scrollContainerRef}
        data-testid="conversation-scroll"
        onScroll={handleConversationScroll}
        className="flex min-h-0 flex-1 flex-col items-center overflow-y-auto overscroll-contain scroll-smooth pb-36 [scrollbar-gutter:stable]"
      >
        <main
          className={`flex w-full max-w-[800px] shrink-0 flex-col px-4 transition-all duration-500 md:px-8 ${
            hasStarted ? "justify-start py-6" : "min-h-[70dvh] items-center justify-center py-12"
          }`}
        >
          {!hasStarted ? (
            <>
              <MascotSlot state="welcome" size="lg" className="mb-4" />
              <h1 className="mb-3 text-center text-2xl font-bold text-text-primary">
                {mode === "professional" ? "从临床问题到可追溯证据" : "今天想弄明白什么？"}
              </h1>
              <p className="mb-8 max-w-md text-center text-sm text-text-secondary">
                {mode === "professional"
                  ? "按 PICO 思路拆解问题，检索并核验证据，呈现证据等级、适用人群、局限与可追溯引用。"
                  : "别被健康传言绕晕：我会先给你清楚答案，再把依据、注意事项和下一步讲明白。也支持体检报告与图片。"}
              </p>
              <div className="grid w-full grid-cols-1 gap-3 md:grid-cols-2">
                {(mode === "professional" ? professionalSuggestions : lifeSuggestions).map((suggestion) => (
                  <button
                    type="button"
                    key={suggestion}
                    onClick={() => void handleSend(suggestion, null)}
                    className="rounded-xl border border-border-divider bg-white p-3 text-left text-sm text-text-primary shadow-sm transition-colors hover:border-brand/30 hover:bg-black/5"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div className="flex w-full flex-col gap-6">
              {messages.map((message, index) => (
                <div id={`message-${message.id}`} key={message.id} className="w-full [content-visibility:auto]">
                  {message.role === "user" ? (
                    <div className="mb-4 flex flex-col items-end">
                      {message.file ? (
                        <div className="mb-1.5 flex items-center gap-2 rounded-xl border border-border-divider/70 bg-bg-page px-3 py-1.5 text-xs text-text-secondary">
                          {message.file.type.startsWith("image/") ? <ImageIcon size={14} /> : <FileText size={14} />}
                          <span className="max-w-[180px] truncate">{message.file.name}</span>
                        </div>
                      ) : null}
                      {message.content ? (
                        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand px-4 py-2.5 text-sm leading-relaxed text-white shadow-xs">
                          {message.content}
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="mb-6 flex w-full items-start gap-3">
                      <MascotSlot state={mascotStateForMessage(message)} size="md" className="mt-1" />
                      <div className="min-w-0 flex-1">
                        <ModuleRenderer
                          modulePlan={message.modulePlan ?? []}
                          runPhase={message.runState?.phase}
                        />
                        {message.runState?.streamedText && !message.modulePlan?.length ? (
                          <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-primary">
                            {message.runState.streamedText}
                          </p>
                        ) : null}
                        <RunStatus state={message.runState} onRetry={() => retryAt(index)} />
                        {message.runState?.phase === "ready" && !isCrisisMessage(message) ? (
                          <div className="flex gap-1 text-text-secondary">
                            <button
                              type="button"
                              onClick={() => navigator.clipboard.writeText(message.modulePlan?.[0]?.props?.conclusion as string ?? "")}
                              className="rounded-lg p-2 hover:bg-black/5"
                              aria-label="复制结论"
                            >
                              <Copy size={14} />
                            </button>
                            <button
                              type="button"
                              onClick={() => retryAt(index)}
                              className="rounded-lg p-2 hover:bg-black/5"
                              aria-label="重新生成"
                            >
                              <RotateCcw size={14} />
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      {showJumpToBottom ? (
        <button
          type="button"
          onClick={jumpToBottom}
          aria-label="回到最新回答"
          className="absolute bottom-32 right-4 z-20 flex items-center gap-1.5 rounded-full border border-border-divider bg-white px-3 py-2 text-xs font-medium text-text-primary shadow-lg hover:bg-bg-page md:right-8"
        >
          <ArrowDown size={15} /> 回到底部
        </button>
      ) : null}

      <div className="absolute bottom-0 z-10 flex w-full justify-center bg-gradient-to-t from-bg-main via-bg-main to-transparent px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-10 md:px-8">
        <div className="w-full max-w-[800px]">
          <Composer
            onSend={handleSend}
            onStop={handleStop}
            state={composerState}
            errorMessage={errorMessage}
            responseMode={mode}
          />
        </div>
      </div>
    </div>
  );
}
