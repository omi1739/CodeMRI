from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("github_owner", "github_name", name="uq_repo_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    github_name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    visibility: Mapped[str | None] = mapped_column(String(32))
    primary_language: Mapped[str | None] = mapped_column(String(64))
    stars: Mapped[int | None] = mapped_column(Integer)
    size_kb: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scans: Mapped[list[Scan]] = relationship(back_populates="repository")


class Scan(Base):
    __tablename__ = "scans"
    __table_args__ = (Index("ix_scans_repository_created", "repository_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    branch: Mapped[str | None] = mapped_column(String(255))
    target_mode: Mapped[str] = mapped_column(String(32), default="portfolio")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    current_stage: Mapped[str | None] = mapped_column(String(64))
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(32))
    config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    analyzer_versions_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    fingerprint_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository: Mapped[Repository] = relationship(back_populates="scans")
    analyzer_runs: Mapped[list[AnalyzerRun]] = relationship(back_populates="scan")
    findings: Mapped[list[Finding]] = relationship(back_populates="scan")
    scores: Mapped[list[Score]] = relationship(back_populates="scan")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="scan")


class AnalyzerRun(Base):
    __tablename__ = "analyzer_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False)
    analyzer: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    finding_count: Mapped[int | None] = mapped_column(Integer)
    raw_artifact_path: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)

    scan: Mapped[Scan] = relationship(back_populates="analyzer_runs")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_scan_severity", "scan_id", "severity"),
        Index("ix_findings_scan_rule", "scan_id", "rule_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    analyzer: Mapped[str] = mapped_column(String(64), nullable=False)
    group_key: Mapped[str | None] = mapped_column(String(255))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    fingerprint_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scan: Mapped[Scan] = relationship(back_populates="findings")
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )

    @property
    def code(self) -> str:
        return f"F-{self.id}"


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_finding", "finding_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id"), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512))
    line_start: Mapped[int | None] = mapped_column(Integer)
    line_end: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[str | None] = mapped_column(String(255))
    metric_name: Mapped[str | None] = mapped_column(String(64))
    metric_value: Mapped[float | None] = mapped_column(Float)
    snippet: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(255), default="")

    finding: Mapped[Finding] = relationship(back_populates="evidence")


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("scan_id", "category", name="uq_score_scan_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    explanation_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    scan: Mapped[Scan] = relationship(back_populates="scores")


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_scan_rank", "scan_id", "rank"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="")
    expected_impact: Mapped[str | None] = mapped_column(String(255))
    effort: Mapped[str] = mapped_column(String(1), default="M")
    finding_ids: Mapped[list[Any] | None] = mapped_column(JSON)

    scan: Mapped[Scan] = relationship(back_populates="recommendations")


class FileInventory(Base):
    __tablename__ = "file_inventory"
    __table_args__ = (Index("ix_file_inventory_scan_path", "scan_id", "path"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str | None] = mapped_column(String(64))
    loc: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ignored: Mapped[bool] = mapped_column(Boolean, default=False)


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    __table_args__ = (Index("ix_graph_edges_scan", "scan_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False)
    from_path: Mapped[str] = mapped_column(String(512), nullable=False)
    to_path: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="import")
