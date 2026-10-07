from __future__ import annotations

from pathlib import Path

from app.analyzers.base import ScanContext
from app.analyzers.fingerprint.analyzer import FingerprintAnalyzer
from app.analyzers.fingerprint.inventory import build_inventory


def _ctx(path: Path) -> ScanContext:
    return ScanContext(scan_id="1", source_dir=str(path))


def test_inventory_counts_and_flags(clean_js: Path) -> None:
    entries = build_inventory(clean_js, max_files=1000, max_file_size_kb=1024)
    paths = {e.path for e in entries}
    assert "package.json" in paths
    assert "index.js" in paths
    assert "test/add.test.js" in paths
    test_entry = next(e for e in entries if e.path == "test/add.test.js")
    assert test_entry.is_test
    js_entry = next(e for e in entries if e.path == "index.js")
    assert js_entry.loc > 0


def test_inventory_ignores_node_modules(tmp_path: Path) -> None:
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("x = 1")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("let a = 1;")
    entries = build_inventory(tmp_path, max_files=1000, max_file_size_kb=1024)
    assert {e.path for e in entries} == {"src/a.js"}


def test_fingerprint_clean_js(clean_js: Path) -> None:
    analyzer = FingerprintAnalyzer()
    ctx = _ctx(clean_js)
    findings = analyzer.run(ctx)
    rules = [f.rule_id for f in findings]
    assert "FP-001" in rules
    assert "FP-002" not in rules
    assert ctx.fingerprint["package_manager"] == "npm"
    assert ctx.fingerprint["package_json_found"] is True
    assert ctx.fingerprint["license"] is True
    assert ctx.fingerprint["readme"] is True
    assert ctx.fingerprint["test_file_count"] == 1
    fp = next(f for f in findings if f.rule_id == "FP-001")
    assert fp.severity == "info"
    assert fp.evidence and fp.evidence[0].reason == "stack_summary"


def test_fingerprint_detects_frameworks_and_flags(almost_no_tests: Path) -> None:
    analyzer = FingerprintAnalyzer()
    ctx = _ctx(almost_no_tests)
    findings = analyzer.run(ctx)
    assert "FP-001" in [f.rule_id for f in findings]
    assert "Express" in ctx.fingerprint["frameworks"]
    assert ctx.fingerprint["test_file_count"] == 0
    assert ctx.fingerprint["readme"] is False


def test_fingerprint_circular_fixture(circular_deps: Path) -> None:
    analyzer = FingerprintAnalyzer()
    ctx = _ctx(circular_deps)
    findings = analyzer.run(ctx)
    assert "FP-001" in [f.rule_id for f in findings]
    # no lockfile -> not a fingerprint concern, but inventory sees both modules
    paths = {e["path"] for e in ctx.inventory}
    assert {"a.js", "b.js"} <= paths


def test_fingerprint_no_package_json(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('hi')\n")
    analyzer = FingerprintAnalyzer()
    ctx = _ctx(tmp_path)
    findings = analyzer.run(ctx)
    assert "FP-002" in [f.rule_id for f in findings]
    assert findings[0].severity == "info"
