from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from app.analyzers.base import Analyzer, ScanContext
from app.analyzers.architecture.analyzer import ArchitectureAnalyzer
from app.analyzers.dependencies.analyzer import DependencyAnalyzer
from app.analyzers.deployment.analyzer import DeploymentAnalyzer
from app.analyzers.documentation.analyzer import DocumentationAnalyzer
from app.analyzers.fingerprint.analyzer import FingerprintAnalyzer
from app.analyzers.git_hygiene.analyzer import GitHygieneAnalyzer
from app.analyzers.quality.analyzer import QualityAnalyzer
from app.analyzers.security.analyzer import SecurityAnalyzer
from app.analyzers.testing.analyzer import TestingAnalyzer
from app.core.config import settings
from app.db.models import AnalyzerRun, Scan
from app.db.session import SessionLocal
from app.evidence.normalize import normalize_findings
from app.github.client import GitHubError, get_branch_sha
from app.github.fetch import download_tarball, safe_extract_tarball
from app.scoring.engine import compute_scores

log = logging.getLogger(__name__)

STAGE_PROGRESS = {
    "queued": 0,
    "fetching": 10,
    "fingerprinting": 30,
    "analyzing": 60,
    "scoring": 85,
    "reporting": 95,
    "completed": 100,
    "failed": 100,
}

ANALYZERS: list[Analyzer] = [
    FingerprintAnalyzer(),
    DependencyAnalyzer(),
    SecurityAnalyzer(),
    QualityAnalyzer(),
    TestingAnalyzer(),
    DocumentationAnalyzer(),
    ArchitectureAnalyzer(),
    GitHygieneAnalyzer(),
    DeploymentAnalyzer(),
]


def run_scan(scan_id: int) -> None:
    session = SessionLocal()
    scan_dir = settings.scans_dir / str(scan_id)
    source_dir: Path | None = None

    try:
        scan = session.get(Scan, scan_id)
        if scan is None:
            log.warning("scan_not_found scan_id=%s", scan_id)
            return

        scan.status = "fetching"
        scan.current_stage = "fetching"
        scan.progress_pct = STAGE_PROGRESS["fetching"]
        scan.started_at = datetime.now(timezone.utc)
        session.commit()

        repository = scan.repository
        owner, name = repository.github_owner, repository.github_name
        branch = scan.branch or repository.default_branch or "main"

        sha = get_branch_sha(owner, name, branch)
        scan.commit_sha = sha
        session.commit()

        scan_dir.mkdir(parents=True, exist_ok=True)
        tarball = download_tarball(owner, name, sha, scan_dir / "source.tar.gz")
        source_dir = safe_extract_tarball(tarball, scan_dir / "src")

        ctx = ScanContext(
            scan_id=str(scan.id),
            source_dir=str(source_dir),
            commit_sha=sha,
            repository_url=repository.url,
            target=scan.target_mode,
        )

        _set_stage(scan, session, "fingerprinting")

        analyzer_versions: dict[str, str] = {}
        for analyzer in ANALYZERS:
            if analyzer.name != "fingerprint":
                _set_stage(scan, session, "analyzing")
            started = time.monotonic()
            run_row = AnalyzerRun(
                scan_id=scan.id,
                analyzer=analyzer.name,
                version=analyzer.version,
                status="running",
            )
            session.add(run_row)
            session.commit()

            try:
                findings = analyzer.run(ctx)
                elapsed_ms = int((time.monotonic() - started) * 1000)
                artifact_dir = scan_dir / "artifacts"
                artifact_dir.mkdir(parents=True, exist_ok=True)
                artifact_path = artifact_dir / f"{analyzer.name}.json"
                artifact_path.write_text(
                    json.dumps([f.model_dump() for f in findings], indent=2, default=str),
                    encoding="utf-8",
                )
                stored = normalize_findings(session, scan.id, findings)
                run_row.status = "completed"
                run_row.duration_ms = elapsed_ms
                run_row.finding_count = len(stored)
                run_row.raw_artifact_path = str(artifact_path)
                analyzer_versions[analyzer.name] = analyzer.version
            except Exception as exc:  # noqa: BLE001 - one analyzer must not kill the scan
                log.exception("analyzer_failed scan_id=%s analyzer=%s", scan.id, analyzer.name)
                run_row.status = "failed"
                run_row.duration_ms = int((time.monotonic() - started) * 1000)
                run_row.error_message = str(exc)[:1000]
            session.commit()

        scan.fingerprint_json = ctx.fingerprint
        scan.analyzer_versions_json = analyzer_versions

        _set_stage(scan, session, "scoring")
        session.flush()
        rows = [f for f in scan.findings]
        result = compute_scores(rows, scan.target_mode)

        scan.overall_score = result.overall
        scan.label = result.label

        from app.db.models import Recommendation, Score

        for existing in list(scan.scores):
            session.delete(existing)
        for existing in list(scan.recommendations):
            session.delete(existing)

        for category in result.categories:
            session.add(
                Score(
                    scan_id=scan.id,
                    category=category.category,
                    score=category.score,
                    weight=category.weight,
                    explanation_json={"penalty": category.penalty, "items": category.explanation},
                )
            )
        for rec in result.recommendations:
            session.add(
                Recommendation(
                    scan_id=scan.id,
                    rank=rec.rank,
                    title=rec.title,
                    explanation=rec.explanation,
                    expected_impact=rec.expected_impact,
                    effort=rec.effort,
                    finding_ids=rec.finding_ids,
                )
            )

        _set_stage(scan, session, "reporting")
        scan.status = "completed"
        scan.current_stage = "completed"
        scan.progress_pct = 100
        scan.finished_at = datetime.now(timezone.utc)
        session.commit()
        log.info("scan_completed scan_id=%s score=%s", scan.id, scan.overall_score)

    except GitHubError as exc:
        _fail(session, scan_id, str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("scan_failed scan_id=%s", scan_id)
        _fail(session, scan_id, f"Unexpected error: {exc}")
    finally:
        session.close()
        if source_dir is not None:
            shutil.rmtree(source_dir, ignore_errors=True)  # keep artifacts only


def _set_stage(scan: Scan, session, stage: str) -> None:
    scan.status = stage
    scan.current_stage = stage
    scan.progress_pct = STAGE_PROGRESS.get(stage, scan.progress_pct)
    session.commit()


def _fail(session, scan_id: int, message: str) -> None:
    try:
        scan = session.get(Scan, scan_id)
        if scan is not None:
            scan.status = "failed"
            scan.current_stage = "failed"
            scan.progress_pct = 100
            scan.error_message = message[:2000]
            scan.finished_at = datetime.now(timezone.utc)
            session.commit()
    except Exception:  # noqa: BLE001
        log.exception("failed_to_mark_scan_failed scan_id=%s", scan_id)
