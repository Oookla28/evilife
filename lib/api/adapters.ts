import type { ModulePlanItem, OrchestrateResponse } from "./types";

export interface EvidenceCitation {
  id: string;
  sourceId?: string;
  title: string;
  year?: number;
  sourceType?: string;
  organization?: string;
  url?: string;
}

type UnknownRecord = Record<string, unknown>;

const asRecord = (value: unknown): UnknownRecord =>
  typeof value === "object" && value !== null ? (value as UnknownRecord) : {};

const asString = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim() ? value : undefined;

const asStringArray = (value: unknown): string[] | undefined =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : undefined;

const normalizeStrength = (value: unknown) => {
  const normalized = asString(value)?.toLowerCase();
  return ["high", "medium", "low", "insufficient"].includes(normalized ?? "")
    ? normalized
    : undefined;
};

export const normalizeCitation = (value: unknown, index: number): EvidenceCitation => {
  const citation = asRecord(value);
  return {
    id:
      asString(citation.evidence_id) ??
      asString(citation.id) ??
      `E${index + 1}`,
    sourceId: asString(citation.source_id),
    title:
      asString(citation.title) ??
      asString(citation.text) ??
      asString(citation.organization) ??
      "未命名来源",
    year: typeof citation.year === "number" ? citation.year : undefined,
    sourceType: asString(citation.source_type) ?? asString(citation.journal),
    organization: asString(citation.organization),
    url: asString(citation.url),
  };
};

export const adaptModule = (
  module: ModulePlanItem,
  response?: Pick<OrchestrateResponse, "request_id" | "run_id" | "timing_ms">
): ModulePlanItem => {
  if (module.type !== "EvidenceAnswer") return module;

  const props = asRecord(module.props);
  const rawCitations = Array.isArray(props.citations)
    ? props.citations
    : Array.isArray(props.sources)
      ? props.sources
      : [];

  return {
    ...module,
    props: {
      ...props,
      evidence_strength:
        normalizeStrength(props.evidence_strength) ?? normalizeStrength(props.strength),
      target_population:
        asStringArray(props.target_population) ??
        (asString(props.target_audience) ? [asString(props.target_audience)] : []),
      non_target_population: asStringArray(props.non_target_population) ?? [],
      general_advice: asStringArray(props.general_advice) ?? [],
      limitations: asStringArray(props.limitations) ?? [],
      citations: rawCitations.map(normalizeCitation),
      debug: response
        ? {
            requestId: response.request_id,
            runId: response.run_id,
            timingMs: response.timing_ms,
          }
        : props.debug,
    },
  };
};

export const adaptModulePlan = (
  modulePlan: ModulePlanItem[],
  response?: Pick<OrchestrateResponse, "request_id" | "run_id" | "timing_ms">
) => modulePlan.map((module) => adaptModule(module, response));
