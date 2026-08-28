import { apiClient } from "./client";
import type { FastRecord } from "./fasting";
import type { ObservationRecord } from "./health-profile";

export interface TodayMealRecord {
  id: string;
  action_id: string;
  created_at: string;
  estimated_total_calories: [number, number];
  estimated_total_calories_center?: number;
  status: "confirmed";
}

export interface TodayRecords {
  date: string;
  fasts: FastRecord[];
  meals: TodayMealRecord[];
  observations: ObservationRecord[];
}

export const getTodayRecords = async (dateStr: string): Promise<TodayRecords> => {
  return await apiClient<TodayRecords>(`/api/v1/today?date=${dateStr}`);
};
