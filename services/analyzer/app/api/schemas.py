from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TargetMode = Literal["portfolio", "university", "production"]


class ScanCreate(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    target: TargetMode = "portfolio"

    @field_validator("url")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class AnalyzerRunOut(BaseModel):
    analyzer: str
    version: str | None = None
    status: str
    duration_ms: int | None = None
    finding_count: int | None = None
    error_message: str | None = None


class ScanStatusOut(BaseModel):
    scan_id: int
    status: str
    current_stage: str | None = None
    progress_pct: int
    target: str
    repository: str
    repository_url: str
    branch: str | None = None
    commit_sha: str | None = None
    overall_score: int | None = None
    label: str | None = None
    error_message: str | None = None
    created_at: str
    analyzer_runs: list[AnalyzerRunOut] = []


class EvidenceOut(BaseModel):
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    symbol: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    snippet: str | None = None
    reason: str
    permalink: str | None = None


class FindingOut(BaseModel):
    id: str
    category: str
    rule_id: str
    title: str
    severity: str
    confidence: str
    description: str
    recommendation: str
    analyzer: str
    occurrence_count: int
    evidence: list[EvidenceOut] = []


class ScoreOut(BaseModel):
    category: str
    score: int
    weight: float
    penalty: float
    items: list[dict[str, Any]] = []


class RecommendationOutModel(BaseModel):
    rank: int
    title: str
    explanation: str
    expected_impact: str
    effort: str
    finding_ids: list[str] = []


class ReportOut(BaseModel):
    scan_id: int
    status: str
    repository: str
    repository_url: str
    branch: str | None
    commit_sha: str | None
    target: str
    overall_score: int | None
    label: str | None
    finished_at: str | None
    counts: dict[str, int]
    severity_counts: dict[str, int]
    fingerprint: dict[str, Any] | None
    scores: list[ScoreOut]
    recommendations: list[RecommendationOutModel]
    analyzer_versions: dict[str, Any] | None


class ScanHistoryItem(BaseModel):
    scan_id: int
    status: str
    target: str
    overall_score: int | None
    label: str | None
    commit_sha: str | None
    created_at: str


class ScanHistoryEntry(ScanHistoryItem):
    repository: str
    repository_url: str


class TargetComparison(BaseModel):
    target: str
    overall_score: int
    label: str


class ComparisonOut(BaseModel):
    scan_id: int
    current_target: str
    current_score: int | None
    comparisons: list[TargetComparison]
