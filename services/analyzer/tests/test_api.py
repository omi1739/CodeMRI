from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize(
    "url",
    ["https://example.com/a/b", "nonsense", "https://github.com/owner"],
)
def test_create_scan_rejects_bad_urls(client: TestClient, url: str) -> None:
    response = client.post("/api/scans", json={"url": url, "target": "portfolio"})
    assert response.status_code == 422


def test_create_scan_rejects_bad_target(client: TestClient) -> None:
    response = client.post(
        "/api/scans", json={"url": "https://github.com/a/b", "target": "enterprise"}
    )
    assert response.status_code == 422


def test_missing_scan_404(client: TestClient) -> None:
    assert client.get("/api/scans/999999").status_code == 404
    assert client.get("/api/findings/999999").status_code == 404
    assert client.get("/api/scans/999999/report").status_code == 404


def test_create_scan_stubs_github(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /scans creates a queued scan without touching the real GitHub API."""
    from app.api import scans as scans_module
    from app.github.client import RepoMetadata

    metadata = RepoMetadata(
        owner="acme",
        name="widget",
        full_name="acme/widget",
        html_url="https://github.com/acme/widget",
        default_branch="main",
        visibility="public",
        primary_language="TypeScript",
        stars=42,
        size_kb=100,
        archived=False,
        pushed_at="2026-01-01T00:00:00Z",
    )
    monkeypatch.setattr(scans_module, "get_repo_metadata", lambda owner, name: metadata)
    monkeypatch.setattr(scans_module, "run_scan", lambda scan_id: None)

    with TestClient(app) as client:
        response = client.post(
            "/api/scans",
            json={"url": "https://github.com/acme/widget/tree/main", "target": "production"},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["repository"] == "acme/widget"
        assert body["branch"] == "main"
        assert body["target"] == "production"

        status = client.get(f"/api/scans/{body['scan_id']}")
        assert status.status_code == 200
        assert status.json()["scan_id"] == body["scan_id"]

        # cleanup: the stubbed background task never finishes the scan, and the
        # per-IP rate limit would otherwise block later test runs.
        from app.db.session import engine
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM scans WHERE id = :i"), {"i": body["scan_id"]})


def _seed_completed_scan() -> int:
    from app.db.models import Finding, Repository, Scan
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        repo = session.query(Repository).filter_by(github_owner="acme", github_name="widget").one_or_none()
        if repo is None:
            repo = Repository(
                github_owner="acme",
                github_name="widget",
                url="https://github.com/acme/widget",
            )
            session.add(repo)
            session.flush()
        scan = Scan(
            repository_id=repo.id,
            branch="main",
            target_mode="portfolio",
            status="completed",
            current_stage="completed",
            progress_pct=100,
            overall_score=72,
            label="Good",
        )
        session.add(scan)
        session.flush()
        session.add(
            Finding(
                scan_id=scan.id,
                category="security",
                rule_id="SEC-001",
                title="Secret detected",
                severity="high",
                confidence="high",
                description="demo",
                recommendation="rotate",
                analyzer="security",
            )
        )
        session.add(
            Finding(
                scan_id=scan.id,
                category="testing",
                rule_id="TST-001",
                title="No tests",
                severity="high",
                confidence="high",
                description="demo",
                recommendation="add tests",
                analyzer="testing",
            )
        )
        session.commit()
        return scan.id
    finally:
        session.close()


def test_history_lists_scans() -> None:
    from app.db.session import engine
    from sqlalchemy import text

    scan_id = _seed_completed_scan()

    with TestClient(app) as client:
        response = client.get("/api/scans")
        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        entry = next(i for i in items if i["scan_id"] == scan_id)
        assert entry["repository"] == "acme/widget"
        assert entry["status"] == "completed"
        assert entry["overall_score"] == 72

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM findings WHERE scan_id = :i"), {"i": scan_id})
        conn.execute(text("DELETE FROM scans WHERE id = :i"), {"i": scan_id})


def test_comparison_returns_all_targets() -> None:
    from app.db.session import engine
    from sqlalchemy import text

    scan_id = _seed_completed_scan()

    with TestClient(app) as client:
        response = client.get(f"/api/scans/{scan_id}/comparison")
        assert response.status_code == 200
        body = response.json()
        assert body["scan_id"] == scan_id
        modes = {c["target"] for c in body["comparisons"]}
        assert modes == {"portfolio", "university", "production"}
        assert all(c["overall_score"] is not None for c in body["comparisons"])
        production = next(c for c in body["comparisons"] if c["target"] == "production")
        portfolio = next(c for c in body["comparisons"] if c["target"] == "portfolio")
        # production raises security/testing weights + severity multiplier => penalty can't drop
        assert production["overall_score"] <= portfolio["overall_score"]

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM findings WHERE scan_id = :i"), {"i": scan_id})
        conn.execute(text("DELETE FROM scans WHERE id = :i"), {"i": scan_id})
