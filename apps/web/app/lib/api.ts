export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type TargetMode = "portfolio" | "university" | "production";
export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface AnalyzerRun {
  analyzer: string;
  version: string | null;
  status: string;
  duration_ms: number | null;
  finding_count: number | null;
  error_message: string | null;
}

export interface ScanStatus {
  scan_id: number;
  status: "queued" | "fetching" | "fingerprinting" | "analyzing" | "scoring" | "reporting" | "completed" | "failed";
  current_stage: string | null;
  progress_pct: number;
  target: string;
  repository: string;
  repository_url: string;
  branch: string | null;
  commit_sha: string | null;
  overall_score: number | null;
  label: string | null;
  error_message: string | null;
  created_at: string;
  analyzer_runs: AnalyzerRun[];
}

export interface EvidenceItem {
  file_path: string | null;
  line_start: number | null;
  line_end: number | null;
  symbol: string | null;
  metric_name: string | null;
  metric_value: number | null;
  snippet: string | null;
  reason: string;
  permalink: string | null;
}

export interface FindingSummary {
  id: string;
  category: string;
  rule_id: string;
  title: string;
  severity: string;
  confidence: string;
  occurrence_count: number;
}

export interface FindingDetail {
  id: string;
  category: string;
  rule_id: string;
  title: string;
  severity: string;
  confidence: string;
  description: string;
  recommendation: string;
  analyzer: string;
  occurrence_count: number;
  evidence: EvidenceItem[];
}

export interface ScoreItem {
  rule_id?: string;
  title?: string;
  count?: number;
  penalty?: number;
  [key: string]: unknown;
}

export interface CategoryScore {
  category: string;
  score: number;
  weight: number;
  penalty: number;
  items: ScoreItem[];
}

export interface Recommendation {
  rank: number;
  title: string;
  explanation: string;
  expected_impact: string;
  effort: string;
  finding_ids: string[];
}

export interface Fingerprint {
  package_json_found?: boolean;
  package_manager?: string | null;
  languages?: string[];
  frameworks?: string[];
  databases?: string[];
  test_frameworks?: string[];
  total_loc?: number;
  file_count?: number;
  test_file_count?: number;
  scripts?: string[];
  typescript?: boolean;
  docker?: boolean;
  ci?: boolean;
  env_example?: boolean;
  license?: boolean;
  readme?: boolean;
}

export interface Report {
  scan_id: number;
  status: string;
  repository: string;
  repository_url: string;
  branch: string | null;
  commit_sha: string | null;
  target: string;
  overall_score: number | null;
  label: string | null;
  finished_at: string | null;
  counts: Record<string, number>;
  severity_counts: Record<Severity, number>;
  fingerprint: Fingerprint | null;
  scores: CategoryScore[];
  recommendations: Recommendation[];
  analyzer_versions: Record<string, string> | null;
}

export interface FindingsPage {
  total: number;
  limit: number;
  offset: number;
  items: FindingSummary[];
}

export interface ScanHistoryEntry {
  scan_id: number;
  status: string;
  target: string;
  overall_score: number | null;
  label: string | null;
  commit_sha: string | null;
  created_at: string;
  repository: string;
  repository_url: string;
}

export interface TargetComparison {
  target: TargetMode;
  overall_score: number;
  label: string;
}

export interface Comparison {
  scan_id: number;
  current_target: string;
  current_score: number | null;
  comparisons: TargetComparison[];
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body?.detail) && body.detail.length > 0) {
        const first = body.detail[0] as { msg?: string };
        detail = first?.msg ?? detail;
      }
    } catch {
      // keep fallback message
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export function createScan(url: string, target: TargetMode): Promise<ScanStatus> {
  return request<ScanStatus>("/api/scans", {
    method: "POST",
    body: JSON.stringify({ url, target }),
  });
}

export function getScan(scanId: number): Promise<ScanStatus> {
  return request<ScanStatus>(`/api/scans/${scanId}`);
}

export function getReport(scanId: number): Promise<Report> {
  return request<Report>(`/api/scans/${scanId}/report`);
}

export interface FindingsQuery {
  limit?: number;
  offset?: number;
  category?: string;
  severity?: string;
}

export function listFindings(scanId: number, query: FindingsQuery = {}): Promise<FindingsPage> {
  const params = new URLSearchParams();
  if (query.limit != null) params.set("limit", String(query.limit));
  if (query.offset != null) params.set("offset", String(query.offset));
  if (query.category) params.set("category", query.category);
  if (query.severity) params.set("severity", query.severity);
  const qs = params.toString();
  return request<FindingsPage>(`/api/scans/${scanId}/findings${qs ? `?${qs}` : ""}`);
}

export function getFinding(id: string): Promise<FindingDetail> {
  const numeric = id.replace(/^F-/, "");
  return request<FindingDetail>(`/api/findings/${numeric}`);
}

export function listScans(limit = 25): Promise<ScanHistoryEntry[]> {
  return request<ScanHistoryEntry[]>(`/api/scans?limit=${limit}`);
}

export function getComparison(scanId: number): Promise<Comparison> {
  return request<Comparison>(`/api/scans/${scanId}/comparison`);
}

export function shortSha(sha: string | null): string {
  return sha ? sha.slice(0, 7) : "";
}

export function formatMs(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}