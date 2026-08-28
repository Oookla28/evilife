import { apiClient } from "./client";

export const getHistory = async (cursor?: string, limit: number = 20) => {
  const params = new URLSearchParams();
  if (cursor) params.append("cursor", cursor);
  params.append("limit", limit.toString());
  
  return await apiClient(`/api/v1/history?${params.toString()}`);
};

export const getHistoryItem = async (id: string) => {
  return await apiClient(`/api/v1/history/${id}`);
};
