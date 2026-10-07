from __future__ import annotations

from pathlib import Path

import pytest

from app.analyzers.base import ScanContext
from app.analyzers.dependencies.analyzer import DependencyAnalyzer, _collect_import_specifiers
from app.analyzers.dependencies.lockfile import (
    collect_dependencies,
    exact_version_from_range,
)


def _ctx(path: Path) -> ScanContext:
    from app.analyzers.fingerprint.inventory import build_inventory, inventory_as_dicts

    entries = build_inventory(path, max_files=2000, max_file_size_kb=1024)
    return ScanContext(scan_id="1", source_dir=str(path), inventory=inventory_as_dicts(entries))


def test_exact_version_parsing() -> None:
    assert exact_version_from_range("1.2.3") == "1.2.3"
    assert exact_version_from_range("v2.0.0") == "2.0.0"
    assert exact_version_from_range("^1.2.3") is None
    assert exact_version_from_range("latest") is None


def test_collect_declared_deps(vulnerable_deps: Path) -> None:
    info = collect_dependencies(vulnerable_deps)
    names = {d.name for d in info.declared}
    assert {"lodash", "minimist"} <= names
    assert info.resolved == {}  # no lockfile
    assert info.lockfiles == []


def test_package_lock_resolution(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"lodash": "^4.17.21"}}', encoding="utf-8"
    )
    (tmp_path / "package-lock.json").write_text(
        '{"lockfileVersion": 3, "packages": {"": {"dependencies": {"lodash": "^4.17.21"}},'
        ' "node_modules/lodash": {"version": "4.17.21"}}}',
        encoding="utf-8",
    )
    info = collect_dependencies(tmp_path)
    assert info.resolved["lodash"] == "4.17.21"
    assert info.lockfiles == ["package-lock.json"]
    assert info.package_managers == ["npm"]


def test_multiple_lockfiles_flag(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name": "x"}', encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
    analyzer = DependencyAnalyzer()
    findings = analyzer.run(_ctx(tmp_path))
    assert "DEP-004" in [f.rule_id for f in findings]
    assert "DEP-003" not in [f.rule_id for f in findings]


def test_no_lockfile_finding(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name": "x", "dependencies": {}}', encoding="utf-8")
    analyzer = DependencyAnalyzer()
    findings = analyzer.run(_ctx(tmp_path))
    assert "DEP-003" in [f.rule_id for f in findings]
    dep3 = next(f for f in findings if f.rule_id == "DEP-003")
    assert dep3.confidence == "high"
    assert dep3.evidence[0].file_path == "package.json"


def test_deepest_resolution_from_exact_pins(vulnerable_deps: Path) -> None:
    analyzer = DependencyAnalyzer()
    ctx = _ctx(vulnerable_deps)
    # mock the network layer so this test never hits npm/OSV
    import app.analyzers.dependencies.analyzer as dep_mod

    original_npm, original_osv = dep_mod.npm_latest_version, dep_mod.osv_query_batch
    dep_mod.npm_latest_version = lambda name: None  # network disabled
    dep_mod.osv_query_batch = lambda queries: [[] for _ in queries]
    try:
        findings = analyzer.run(ctx)
    finally:
        dep_mod.npm_latest_version, dep_mod.osv_query_batch = original_npm, original_osv

    # no lockfile -> DEP-003 present; no DEP-001 because OSV returned empty
    assert "DEP-003" in [f.rule_id for f in findings]
    assert "DEP-001" not in [f.rule_id for f in findings]


def test_deepest_unused_dependency_detection(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"left-pad": "1.0.0", "dotenv": "16.0.0"},'
        ' "devDependencies": {"eslint": "8.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "index.js").write_text('require("dotenv").config();\n', encoding="utf-8")
    analyzer = DependencyAnalyzer()
    ctx = _ctx(tmp_path)

    import app.analyzers.dependencies.analyzer as dep_mod

    original_npm, original_osv = dep_mod.npm_latest_version, dep_mod.osv_query_batch
    dep_mod.npm_latest_version = lambda name: "99.0.0"
    dep_mod.osv_query_batch = lambda queries: [[] for _ in queries]
    try:
        findings = analyzer.run(ctx)
    finally:
        dep_mod.npm_latest_version, dep_mod.osv_query_batch = original_npm, original_osv

    unused = next((f for f in findings if f.rule_id == "DEP-005"), None)
    assert unused is not None
    symbols = [e.symbol for e in unused.evidence]
    assert "left-pad" in symbols
    assert "dotenv" not in symbols  # imported
    assert "eslint" not in symbols  # dev tooling excluded
    assert unused.confidence == "low"


def test_import_collection(tmp_path: Path) -> None:
    (tmp_path / "a.js").write_text(
        'import x from "pkg-a";\nconst y = require("./local");\nimport "@scope/pkg-b/c";\n',
        encoding="utf-8",
    )
    from app.analyzers.fingerprint.inventory import build_inventory, inventory_as_dicts

    entries = inventory_as_dicts(build_inventory(tmp_path, 100, 1024))
    specs = _collect_import_specifiers(tmp_path, entries)
    assert "pkg-a" in specs
    assert "./local" in specs
    assert "@scope/pkg-b/c" in specs
