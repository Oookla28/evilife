import { apiClient } from "./client";
import { ActionConfirmResponse } from "./types";
import { ActionConfirmResponseSchema } from "./schemas";

export interface ConfirmActionParams {
  run_id: string;
  confirmed: boolean;
  client_action_id: string;
  edited_items?: Array<{
    id: string;
    name: string;
    portion: string;
    portion_grams?: [number, number];
    estimated_calories: [number, number];
    estimated_calories_center?: number;
    confidence?: "low" | "medium" | "high";
    reference_basis?: string;
    uncertainty?: string;
  }>;
  estimated_total_calories?: [number, number];
  estimated_total_calories_center?: number;
}

export const confirmAction = async (
  actionId: string, 
  params: ConfirmActionParams
): Promise<ActionConfirmResponse> => {
  const rawData = await apiClient(`/api/v1/actions/${actionId}/confirm`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(params),
  });

  return ActionConfirmResponseSchema.parse(rawData);
};

export const undoAction = async (
  actionId: string, 
  undoToken: string
): Promise<{ success: boolean }> => {
  return await apiClient(`/api/v1/actions/${actionId}/undo`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ undo_token: undoToken }),
  });
};
