import { apiClient } from "./client";
import { OrchestrateResponse } from "./types";
import { OrchestrateResponseSchema } from "./schemas";

export interface OrchestrateParams {
  text?: string;
  image?: File;
  document?: File;
  session_id: string;
  mode: "auto" | "fast" | "deep" | "evaluation";
  signal?: AbortSignal;
}

export const orchestrate = async (params: OrchestrateParams): Promise<OrchestrateResponse> => {
  const formData = new FormData();
  if (params.text) formData.append("text", params.text);
  if (params.image) formData.append("image", params.image);
  if (params.document) formData.append("document", params.document);
  formData.append("session_id", params.session_id);
  formData.append("mode", params.mode);

  const rawData = await apiClient("/api/v1/orchestrate", {
    method: "POST",
    body: formData,
    signal: params.signal,
    // Note: Do not set Content-Type header manually when sending FormData, 
    // the browser will set it with the correct boundary automatically.
  });

  // Validate at runtime
  return OrchestrateResponseSchema.parse(rawData);
};

export const getRunStatus = async (runId: string): Promise<OrchestrateResponse> => {
  const rawData = await apiClient(`/api/v1/runs/${runId}`);
  return OrchestrateResponseSchema.parse(rawData);
};
