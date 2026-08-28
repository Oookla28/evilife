import { apiClient } from "./client";

export interface ReportItem {
  name: string;
  value: string;
  unit: string;
  reference_range: string;
  flag: "high" | "low" | "normal" | "unknown";
}

export interface ReportAnalysis {
  report_id: string;
  file_name: string;
  source: "text_extraction" | "deepseek_vl2" | "limited_fallback";
  summary: string;
  items: ReportItem[];
  limitations: string[];
}

export function analyzeReport(file: File): Promise<ReportAnalysis> {
  const body = new FormData();
  body.append("file", file);
  return apiClient<ReportAnalysis>("/api/v1/reports/analyze", { method: "POST", body });
}
