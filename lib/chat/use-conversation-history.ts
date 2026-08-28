"use client";

import { useCallback, useEffect, useState } from "react";
import { readConversations, type StoredConversation } from "./history-store";

export function useConversationHistory() {
  const [conversations, setConversations] = useState<StoredConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      setConversations(await readConversations());
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "历史记录加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    readConversations()
      .then((items) => {
        if (active) {
          setConversations(items);
          setError("");
        }
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "历史记录加载失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    window.addEventListener("evilife:history-updated", refresh);
    return () => {
      active = false;
      window.removeEventListener("evilife:history-updated", refresh);
    };
  }, [refresh]);

  return { conversations, loading, error, refresh };
}
