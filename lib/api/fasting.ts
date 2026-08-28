import { apiClient } from "./client";

export interface FastRecord {
  id: string;
  start_at: string;
  end_at: string | null;
  goal_hours: number;
  status: "active" | "completed";
}

export function getActiveFast(): Promise<FastRecord | null> {
  return apiClient<FastRecord | null>("/api/v1/fasts/active");
}

export function getFasts(limit = 8): Promise<FastRecord[]> {
  return apiClient<FastRecord[]>(`/api/v1/fasts?limit=${limit}`);
}

export function startFast(goalHours: number): Promise<FastRecord> {
  return apiClient<FastRecord>("/api/v1/fasts/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal_hours: goalHours }),
  });
}

export function endFast(fastId: string): Promise<FastRecord> {
  return apiClient<FastRecord>(`/api/v1/fasts/${fastId}/end`, {
    method: "POST",
  });
}
