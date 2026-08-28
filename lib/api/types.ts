import { z } from "zod";
import {
  ModulePlanItemSchema,
  ActionSchema,
  OrchestrateResponseSchema,
  StreamEventSchema,
  ApiErrorSchema,
  ActionConfirmResponseSchema,
} from "./schemas";

export type ModulePlanItem = z.infer<typeof ModulePlanItemSchema>;
export type Action = z.infer<typeof ActionSchema>;
export type OrchestrateResponse = z.infer<typeof OrchestrateResponseSchema>;
export type StreamEvent = z.infer<typeof StreamEventSchema>;
export type ApiError = z.infer<typeof ApiErrorSchema>;
export type ActionConfirmResponse = z.infer<typeof ActionConfirmResponseSchema>;

export type GateStatus = OrchestrateResponse["gate_status"];
export type ModuleStatus = ModulePlanItem["status"];
export type StreamEventType = StreamEvent["type"];

export interface VerdictEvidenceItem {
  evidence_id: string;
  source_id: string;
  title: string;
  year?: number | null;
  source_type: string;
  organization?: string | null;
  direction: "support" | "against" | "mixed" | "context";
  finding: string;
  url: string;
  channel?: "curated_database" | "live_medical_search" | null;
  reliability_score?: number | null;
}

export interface HealthClaim {
  claim_id: string;
  claim: string;
  type: string;
  original_text: string;
  span_start: number;
  span_end: number;
  source_intent?: string | null;
}

export interface TraceStep {
  step: string;
  action: string;
  tool?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
  observation?: string | null;
  decision?: string | null;
  timestamp?: string;
  latency_ms?: number | null;
  status?: "ok" | "failed" | "degraded" | "skipped";
}

export interface EvidenceNote {
  evidence_id: string;
  source_id: string;
  title: string;
  year?: number | null;
  study_type: string;
  population?: string | null;
  sample_size?: number | null;
  intervention?: string | null;
  comparator?: string | null;
  outcome?: string | null;
  finding: string;
  supports: string[];
  does_not_support: string[];
  limitations: string[];
  applicability?: string | null;
  source_excerpt: string;
  url: string;
  retrieved_at: string;
  direction: "support" | "against" | "mixed" | "context";
}
