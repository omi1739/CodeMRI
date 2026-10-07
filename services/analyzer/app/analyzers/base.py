from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

SEVERITIES = ("critical", "high", "medium", "low", "info")
CONFIDENCES = ("high", "medium", "low")
CATEGORIES = (
    "security",
    "dependencies",
    "code_quality",
    "testing",
    "documentation",
    "architecture",
    "deployment",
    "git_hygiene",
    "maintainability",
    "fingerprint",
)


class Evidence(BaseModel):
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    symbol: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    snippet: str | None = None  # REDACTED if it could contain a secret
    reason: str = ""
    permalink: str | None = None


class Finding(BaseModel):
    category: str
    rule_id: str
    title: str
    severity: str
    confidence: str
    description: str = ""
    recommendation: str = ""
    analyzer: str
    evidence: list[Evidence] = Field(default_factory=list)
    group_key: str | None = None
    occurrence_count: int = 1

    def model_post_init(self, __context: object) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"Invalid severity {self.severity!r} for {self.rule_id}")
        if self.confidence not in CONFIDENCES:
            raise ValueError(f"Invalid confidence {self.confidence!r} for {self.rule_id}")


class ScanContext(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    scan_id: str
    source_dir: str  # read-only extracted source
    commit_sha: str = ""
    repository_url: str = ""
    fingerprint: dict = Field(default_factory=dict)
    target: str = "portfolio"
    # populated during intake so analyzers can reuse work
    inventory: list[dict] = Field(default_factory=list)


@runtime_checkable
class Analyzer(Protocol):
    name: str
    version: str

    def run(self, ctx: ScanContext) -> list[Finding]: ...
