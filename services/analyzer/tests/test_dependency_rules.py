from __future__ import annotations

from pathlib import Path

from app.analyzers.base import ScanContext
from app.analyzers.dependencies.analyzer import DependencyAnalyzer
from app.analyzers.fingerprint.inventory import build_inventory, inventory_as_dicts


def _ctx(path: Path) -> ScanContext:
    entries = build_inventory(path, max_files=2000, max_file_size_kb=1024)
    return ScanContext(scan_id="1", source_dir=str(path), inventory=inventory_as_dicts(entries))


def test_deepest_advisory_exact_match(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"lodash": "4.17.15"}}', encoding="utf-8"
    )
    (tmp_path / "index.js").write_text('require("lodash");\n', encoding="utf-8")

    import app.analyzers.dependencies.analyzer as dep_mod

    seen = {}

    def fake_osv(queries):
        seen["queries"] = queries
        return [
            [
                {
                    "id": "OSV-2020-123",
                    "ghsa": "GHSA-p6mc-m468-83gg",
                    "aliases": ["GHSA-p6mc-m468-83gg", "CVE-2020-8203"],
                    "summary": "Prototype pollution in lodash",
                    "severity_text": "HIGH",
                    "cvss_score": 7.4,
                    "references": [],
                }
            ]
        ]

    original_npm, original_osv = dep_mod.npm_latest_version, dep_mod.osv_query_batch
    dep_mod.npm_latest_version = lambda name: None
    dep_mod.osv_query_batch = fake_osv
    try:
        findings = DependencyAnalyzer().run(_ctx(tmp_path))
    finally:
        dep_mod.npm_latest_version, dep_mod.osv_query_batch = original_npm, original_osv

    dep1 = [f for f in findings if f.rule_id == "DEP-001"]
    assert len(dep1) == 1
    finding = dep1[0]
    assert finding.severity == "high"  # from cvss 7.4
    assert finding.confidence == "high"
    assert "GHSA-p6mc-m468-83gg" in finding.description
    assert seen["queries"][0]["version"] == "4.17.15"  # exact version queried
    assert any("GHSA-p6mc-m468-83gg" in (e.snippet or "") for e in finding.evidence)
    assert finding.group_key == "DEP-001|lodash"


def test_deepest_outdated_grouped(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"lodash": "3.10.1", "chalk": "0.1.0"}}', encoding="utf-8"
    )
    (tmp_path / "index.js").write_text('require("lodash");\nrequire("chalk");\n', encoding="utf-8")

    import app.analyzers.dependencies.analyzer as dep_mod

    originals = (dep_mod.npm_latest_version, dep_mod.osv_query_batch)
    dep_mod.npm_latest_version = lambda name: "4.17.21" if name == "lodash" else "5.0.0"
    dep_mod.osv_query_batch = lambda queries: [[] for _ in queries]
    try:
        findings = DependencyAnalyzer().run(_ctx(tmp_path))
    finally:
        dep_mod.npm_latest_version, dep_mod.osv_query_batch = originals

    dep2 = [f for f in findings if f.rule_id == "DEP-002"]
    assert len(dep2) == 1  # grouped into one finding
    assert dep2[0].occurrence_count == 2
    assert len(dep2[0].evidence) == 2
    symbols = {e.symbol for e in dep2[0].evidence}
    assert {"lodash", "chalk"} <= symbols
