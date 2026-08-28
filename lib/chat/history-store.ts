import { apiClient } from "@/lib/api/client";
import type { ModulePlanItem } from "@/lib/api/types";

export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  content?: string;
  file?: { name: string; type: string };
  modulePlan?: ModulePlanItem[];
}

export interface StoredConversation {
  sessionId: string;
  title: string;
  mode: "life" | "professional";
  updatedAt: string;
  messages: StoredMessage[];
}

interface ConversationWire {
  session_id: string;
  title: string;
  mode: "life" | "professional";
  updated_at: string;
  messages: StoredMessage[];
}

const fromWire = (item: ConversationWire): StoredConversation => ({
  sessionId: item.session_id,
  title: item.title,
  mode: item.mode,
  updatedAt: item.updated_at,
  messages: item.messages,
});

export const readConversations = async (): Promise<StoredConversation[]> => {
  const items = await apiClient<ConversationWire[]>("/api/v1/conversations?limit=50");
  return items.map(fromWire);
};

let saveQueue = Promise.resolve();

export const saveConversation = async (conversation: StoredConversation) => {
  if (conversation.messages.length === 0) return;
  const request = saveQueue.then(async () => {
    await apiClient<ConversationWire>(
      `/api/v1/conversations/${encodeURIComponent(conversation.sessionId)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: conversation.sessionId,
          title: conversation.title,
          mode: conversation.mode,
          messages: conversation.messages,
        }),
      },
    );
    window.dispatchEvent(new Event("evilife:history-updated"));
  });
  saveQueue = request.catch(() => undefined);
  await request;
};

export const deleteConversation = async (sessionId: string) => {
  await apiClient<void>(`/api/v1/conversations/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  window.dispatchEvent(new Event("evilife:history-updated"));
};

export const createSessionId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `session-${Math.random().toString(36).slice(2)}`;
