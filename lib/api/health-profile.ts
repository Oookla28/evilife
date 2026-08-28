import { apiClient } from "./client";

export type ObservationKind =
  | "water_ml"
  | "steps"
  | "sleep_minutes"
  | "weight_kg"
  | "waist_cm"
  | "resting_heart_rate"
  | "mood_score"
  | "note";

export type ObservationSource = "self_report" | "device" | "ai_estimate";

export interface ObservationRecord {
  id: string;
  kind: ObservationKind;
  value: number | null;
  note: string | null;
  source: ObservationSource;
  observed_at: string;
  connector_id?: string | null;
  external_id?: string | null;
}

export type HealthConnectorStatus = "requires_native_bridge" | "requires_credentials" | "available";
export interface HealthConnector {
  id: "apple_healthkit" | "android_health_connect" | "huawei_health_kit" | "generic_import";
  label: string;
  status: HealthConnectorStatus;
  authorization: string;
  transport: string;
  docs_url: string;
  supported_kinds: ObservationKind[];
}
export interface PairingSession {
  id: string;
  connector_id: HealthConnector["id"];
  token: string;
  pairing_url: string;
  expires_at: string;
  status: "pending" | "paired" | "expired";
}
export interface ProfileAnalysisCard {
  tone: "summary" | "population" | "boundary" | "action";
  title: string;
  preview: string;
  details: Array<{ label: string; value: string }>;
}
export interface ProfileAnalysisResponse {
  source: "ai" | "deterministic_fallback";
  cards: ProfileAnalysisCard[];
}

export interface AppleHealthImportSummary {
  source_file: string;
  processed_records: number;
  accepted: number;
  skipped: number;
  date_from: string | null;
  date_to: string | null;
  counts: Partial<Record<ObservationKind, number>>;
}

export interface AppleHealthImportJob {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  processed_records: number;
  summary: AppleHealthImportSummary | null;
  error: string | null;
}

export interface CompletedAppleHealthImport {
  jobId: string;
  summary: AppleHealthImportSummary;
}

export interface ObservationCreate {
  kind: ObservationKind;
  value?: number;
  note?: string;
  source: ObservationSource;
  observed_at?: string;
}

export function addObservation(input: ObservationCreate): Promise<ObservationRecord> {
  return apiClient<ObservationRecord>("/api/v1/observations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function addObservations(inputs: ObservationCreate[]): Promise<ObservationRecord[]> {
  return apiClient<ObservationRecord[]>("/api/v1/observations/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ observations: inputs }),
  });
}

export function getObservations(
  kind?: ObservationKind,
  limit = 100
): Promise<ObservationRecord[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (kind) params.set("kind", kind);
  return apiClient<ObservationRecord[]>(`/api/v1/observations?${params.toString()}`);
}

export function deleteObservation(id: string): Promise<ObservationRecord> {
  return apiClient<ObservationRecord>(`/api/v1/observations/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function getHealthConnectors(): Promise<HealthConnector[]> {
  return apiClient<HealthConnector[]>("/api/v1/health-connectors");
}

export function createHealthPairing(connectorId: HealthConnector["id"]): Promise<PairingSession> {
  return apiClient<PairingSession>(`/api/v1/health-pairing?connector_id=${encodeURIComponent(connectorId)}`, { method: "POST" });
}

export function getHealthPairing(pairingId: string): Promise<PairingSession> {
  return apiClient<PairingSession>(`/api/v1/health-pairing/${encodeURIComponent(pairingId)}`);
}

export function analyzeHealthProfile(): Promise<ProfileAnalysisResponse> {
  return apiClient<ProfileAnalysisResponse>("/api/v1/profile/analyze", { method: "POST" });
}

export function startAppleHealthImport(file: File): Promise<AppleHealthImportJob> {
  const form = new FormData();
  form.append("export", file);
  return apiClient<AppleHealthImportJob>("/api/v1/health-imports/apple", {
    method: "POST",
    body: form,
  });
}

export function getAppleHealthImport(jobId: string): Promise<AppleHealthImportJob> {
  return apiClient<AppleHealthImportJob>(`/api/v1/health-imports/apple/${encodeURIComponent(jobId)}`);
}
