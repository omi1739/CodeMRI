from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from sqlalchemy import case, select
from sqlalchemy.orm import Session, joinedload

from app.api.limits import RateLimitError, check_can_start
from app.api.schemas import (
    ComparisonOut,
    EvidenceOut,
    FindingOut,
    ReportOut,
    RecommendationOutModel,
    ScanCreate,
    ScanHistoryEntry,
    ScanHistoryItem,
    ScanStatusOut,
    ScoreOut,
    TargetComparison,
)
from app.db.models import AnalyzerRun, Finding, Recommendation, Repository, Scan, Score
from app.db.session import SessionLocal
from app.github.client import GitHubError, get_repo_metadata
from app.github.url import InvalidRepoUrl, parse_github_url
from app.scoring.engine import compute_scores
from app.worker import run_scan

router = APIRouter(prefix="/api", tags=["scans"])

TERMINAL_STATUSES = {"completed", "failed"}
SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _permalink(scan: Scan, evidence_item) -> str | None:
    if not evidence_item.file_path or not scan.commit_sha:
        return None
    repo = scan.repository
    url = f"https://github.com/{repo.github_owner}/{repo.github_name}/blob/{scan.commit_sha}/{evidence_item.file_path}"
    if evidence_item.line_start:
        if evidence_item.line_end and evidence_item.line_end != evidence_item.line_start:
            url += f"#L{evidence_item.line_start}-L{evidence_item.line_end}"
        else:
            url += f"#L{evidence_item.line_start}"
    return url


@router.post("/scans", response_model=ScanStatusOut, status_code=202)
def create_scan(payload: ScanCreate, request: Request, background: BackgroundTasks) -> ScanStatusOut:
    try:
        parsed = parse_github_url(payload.url)
    except InvalidRepoUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session = SessionLocal()
    try:
        try:
            metadata = get_repo_metadata(parsed.owner, parsed.name)
        except GitHubError as exc:
            status = 429 if "rate limit" in str(exc).lower() else 404
            raise HTTPException(status_code=status, detail=str(exc)) from exc

        active_ids = list(
            session.execute(
                select(Scan.id).where(Scan.status.not_in(TERMINAL_STATUSES)).limit(50)
            ).scalars()
        )
        active_rows = session.query(Scan).filter(Scan.id.in_(active_ids)).all() if active_ids else []
        ip = _client_ip(request)

        try:
            check_can_start(
                ip,
                is_active_for_ip=lambda addr: any(
                    (row.config_json or {}).get("ip") == addr for row in active_rows
                ),
                active_total=len(active_rows),
            )
        except RateLimitError as exc:
            raise HTTPException(status_code=429, detail=exc.message) from exc

        repository = session.execute(
            select(Repository).where(
                Repository.github_owner == metadata.owner,
                Repository.github_name == metadata.name,
            )
        ).scalar_one_or_none()
        if repository is None:
            repository = Repository(
                github_owner=metadata.owner,
                github_name=metadata.name,
                url=metadata.html_url,
            )
            session.add(repository)
            session.flush()

        repository.default_branch = metadata.default_branch
        repository.visibility = metadata.visibility
        repository.primary_language = metadata.primary_language
        repository.stars = metadata.stars
        repository.size_kb = metadata.size_kb

        scan = Scan(
            repository_id=repository.id,
            branch=parsed.ref or metadata.default_branch,
            target_mode=payload.target,
            status="queued",
            current_stage="queued",
            progress_pct=0,
            config_json={"ip": ip, "requested_url": payload.url},
        )
        session.add(scan)
        session.commit()

        background.add_task(run_scan, scan.id)
        return _status_payload(session, scan)
    finally:
        session.close()


@router.get("/scans/{scan_id}", response_model=ScanStatusOut)
def get_scan(scan_id: int) -> ScanStatusOut:
    session = SessionLocal()
    try:
        scan = _get_scan(session, scan_id)
        return _status_payload(session, scan)
    finally:
        session.close()


@router.get("/scans", response_model=list[ScanHistoryEntry])
def list_recent_scans(limit: int = Query(default=20, ge=1, le=100)) -> list[ScanHistoryEntry]:
    """Recent scans across all repositories, newest first."""
    session = SessionLocal()
    try:
        rows = (
            session.query(Scan)
            .options(joinedload(Scan.repository))
            .order_by(Scan.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            ScanHistoryEntry(
                scan_id=row.id,
                status=row.status,
                target=row.target_mode,
                overall_score=row.overall_score,
                label=row.label,
                commit_sha=row.commit_sha,
                created_at=_iso(row.created_at) or "",
                repository=f"{row.repository.github_owner}/{row.repository.github_name}",
                repository_url=row.repository.url,
            )
            for row in rows
        ]
    finally:
        session.close()


@router.get("/scans/{scan_id}/comparison", response_model=ComparisonOut)
def get_comparison(scan_id: int) -> ComparisonOut:
    """Overall score + label as-if scanned under every target mode."""
    session = SessionLocal()
    try:
        scan = _get_scan(session, scan_id)
        rows = session.query(Finding).filter(Finding.scan_id == scan.id).all()
        comparisons: list[TargetComparison] = []
        for mode in ("portfolio", "university", "production"):
            result = compute_scores(rows, mode)
            comparisons.append(
                TargetComparison(target=mode, overall_score=result.overall, label=result.label)
            )
        return ComparisonOut(
            scan_id=scan.id,
            current_target=scan.target_mode,
            current_score=scan.overall_score,
            comparisons=comparisons,
        )
    finally:
        session.close()


@router.get("/scans/{scan_id}/report", response_model=ReportOut)
def get_report(scan_id: int) -> ReportOut:
    session = SessionLocal()
    try:
        scan = _get_scan(session, scan_id)
        findings = (
            session.query(Finding).filter(Finding.scan_id == scan.id).order_by(Finding.id).all()
        )

        counts: dict[str, int] = {}
        severity_counts = {level: 0 for level in SEVERITY_ORDER}
        for finding in findings:
            counts[finding.category] = counts.get(finding.category, 0) + 1
            if finding.severity in severity_counts:
                severity_counts[finding.severity] += 1

        scores = session.query(Score).filter(Score.scan_id == scan.id).all()
        recommendations = (
            session.query(Recommendation)
            .filter(Recommendation.scan_id == scan.id)
            .order_by(Recommendation.rank)
            .all()
        )

        return ReportOut(
            scan_id=scan.id,
            status=scan.status,
            repository=f"{scan.repository.github_owner}/{scan.repository.github_name}",
            repository_url=scan.repository.url,
            branch=scan.branch,
            commit_sha=scan.commit_sha,
            target=scan.target_mode,
            overall_score=scan.overall_score,
            label=scan.label,
            finished_at=_iso(scan.finished_at),
            counts=counts,
            severity_counts=severity_counts,
            fingerprint=scan.fingerprint_json,
            scores=[
                ScoreOut(
                    category=row.category,
                    score=row.score,
                    weight=row.weight,
                    penalty=float((row.explanation_json or {}).get("penalty", 0)),
                    items=list((row.explanation_json or {}).get("items", [])),
                )
                for row in sorted(scores, key=lambda r: -r.weight)
            ],
            recommendations=[
                RecommendationOutModel(
                    rank=row.rank,
                    title=row.title,
                    explanation=row.explanation,
                    expected_impact=row.expected_impact or "",
                    effort=row.effort,
                    finding_ids=list(row.finding_ids or []),
                )
                for row in recommendations
            ],
            analyzer_versions=scan.analyzer_versions_json,
        )
    finally:
        session.close()


@router.get("/scans/{scan_id}/findings")
def list_findings(
    scan_id: int,
    category: str | None = None,
    severity: str | None = None,
    confidence: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    session = SessionLocal()
    try:
        _get_scan(session, scan_id)
        query = session.query(Finding).filter(Finding.scan_id == scan_id)
        if category:
            query = query.filter(Finding.category == category)
        if severity:
            query = query.filter(Finding.severity == severity)
        if confidence:
            query = query.filter(Finding.confidence == confidence)

        total = query.count()
        severity_rank = case(
            (Finding.severity == "critical", 0),
            (Finding.severity == "high", 1),
            (Finding.severity == "medium", 2),
            (Finding.severity == "low", 3),
            else_=4,
        )
        rows = query.order_by(severity_rank, Finding.id).offset(offset).limit(limit).all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": f"F-{row.id}",
                    "category": row.category,
                    "rule_id": row.rule_id,
                    "title": row.title,
                    "severity": row.severity,
                    "confidence": row.confidence,
                    "occurrence_count": row.occurrence_count,
                }
                for row in rows
            ],
        }
    finally:
        session.close()


@router.get("/findings/{finding_id}", response_model=FindingOut)
def get_finding(finding_id: int) -> FindingOut:
    session = SessionLocal()
    try:
        row = session.get(Finding, finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Finding not found")
        scan = row.scan
        return FindingOut(
            id=f"F-{row.id}",
            category=row.category,
            rule_id=row.rule_id,
            title=row.title,
            severity=row.severity,
            confidence=row.confidence,
            description=row.description,
            recommendation=row.recommendation,
            analyzer=row.analyzer,
            occurrence_count=row.occurrence_count,
            evidence=[
                EvidenceOut(
                    file_path=item.file_path,
                    line_start=item.line_start,
                    line_end=item.line_end,
                    symbol=item.symbol,
                    metric_name=item.metric_name,
                    metric_value=item.metric_value,
                    snippet=item.snippet,
                    reason=item.reason,
                    permalink=_permalink(scan, item),
                )
                for item in row.evidence
            ],
        )
    finally:
        session.close()


@router.get("/repositories/{repository_id}/scans", response_model=list[ScanHistoryItem])
def scan_history(repository_id: int) -> list[ScanHistoryItem]:
    session = SessionLocal()
    try:
        repository = session.get(Repository, repository_id)
        if repository is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        rows = (
            session.query(Scan)
            .filter(Scan.repository_id == repository_id)
            .order_by(Scan.created_at.desc())
            .all()
        )
        return [
            ScanHistoryItem(
                scan_id=row.id,
                status=row.status,
                target=row.target_mode,
                overall_score=row.overall_score,
                label=row.label,
                commit_sha=row.commit_sha,
                created_at=_iso(row.created_at) or "",
            )
            for row in rows
        ]
    finally:
        session.close()


def _get_scan(session: Session, scan_id: int) -> Scan:
    scan = (
        session.query(Scan).options(joinedload(Scan.repository)).filter(Scan.id == scan_id).first()
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


def _status_payload(session: Session, scan: Scan) -> ScanStatusOut:
    runs = session.query(AnalyzerRun).filter(AnalyzerRun.scan_id == scan.id).all()
    repo = scan.repository
    return ScanStatusOut(
        scan_id=scan.id,
        status=scan.status,
        current_stage=scan.current_stage,
        progress_pct=scan.progress_pct,
        target=scan.target_mode,
        repository=f"{repo.github_owner}/{repo.github_name}",
        repository_url=repo.url,
        branch=scan.branch,
        commit_sha=scan.commit_sha,
        overall_score=scan.overall_score,
        label=scan.label,
        error_message=scan.error_message,
        created_at=_iso(scan.created_at) or "",
        analyzer_runs=[
            {
                "analyzer": run.analyzer,
                "version": run.version,
                "status": run.status,
                "duration_ms": run.duration_ms,
                "finding_count": run.finding_count,
                "error_message": run.error_message,
            }
            for run in runs
        ],
    )
