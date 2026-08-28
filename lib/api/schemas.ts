import { z } from "zod";

// Base Module schema
export const ModulePlanItemSchema = z.object({
  module_id: z.string(),
  type: z.string(),
  version: z.string().optional(),
  priority: z.number().optional(),
  status: z.enum(["loading", "ready", "error", "skipped", "pending"]),
  props: z.record(z.string(), z.unknown()).default({}),
});

// Action Schema
export const ActionSchema = z.object({
  action_id: z.string(),
  type: z.string(),
  label: z.string(),
  requires_confirmation: z.boolean(),
  status: z.enum(["pending", "completed", "failed", "cancelled"]),
  payload_preview: z.record(z.string(), z.unknown()).optional(),
});

// Orchestrate Response Schema
export const OrchestrateResponseSchema = z.object({
  request_id: z.string(),
  session_id: z.string(),
  run_id: z.string(),
  intent: z.string().optional(),
  risk_level: z.string().optional(),
  gate_status: z.enum(["normal", "degraded", "refused"]),
  status: z.string(),
  module_plan: z.array(ModulePlanItemSchema),
  actions: z.array(ActionSchema).default([]),
  timing_ms: z.record(z.string(), z.number()).optional(),
});

// SSE Event Schema
export const StreamEventSchema = z.object({
  event_id: z.string(),
  request_id: z.string(),
  run_id: z.string(),
  type: z.enum([
    "run.started",
    "route.selected",
    "evidence.snapshot",
    "answer.delta",
    "module.ready",
    "gate.completed",
    "action.required",
    "run.completed",
    "run.failed",
    "heartbeat"
  ]),
  timestamp: z.string(),
  payload: z.record(z.string(), z.unknown()).optional(),
});

// Error Schema
export const ApiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string().optional(),
    retryable: z.boolean(),
    details: z.record(z.string(), z.unknown()).optional(),
  }),
});

// Action Confirmation Schema
export const ActionConfirmResponseSchema = z.object({
  action_id: z.string(),
  status: z.string(),
  affected_resource: z.object({
    type: z.string(),
    id: z.string(),
  }).optional(),
  undo_token: z.string().optional(),
  undo_expires_at: z.string().optional(),
});
