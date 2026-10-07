from __future__ import annotations

from pathlib import Path

from app.analyzers.architecture.analyzer import ArchitectureAnalyzer
from app.analyzers.base import ScanContext
from app.analyzers.deployment.analyzer import DeploymentAnalyzer
from app.analyzers.documentation.analyzer import DocumentationAnalyzer
from app.analyzers.fingerprint.inventory import build_inventory, inventory_as_dicts
from app.analyzers.git_hygiene.analyzer import GitHygieneAnalyzer
from app.analyzers.quality.analyzer import QualityAnalyzer
from app.analyzers.security.analyzer import SecurityAnalyzer
from app.analyzers.testing.analyzer import TestingAnalyzer


def _ctx(path: Path) -> ScanContext:
    entries = build_inventory(path, max_files=2000, max_file_size_kb=1024)
    return ScanContext(scan_id="1", source_dir=str(path), inventory=inventory_as_dicts(entries))


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------- security

def test_security_secrets_are_masked(secrets: Path) -> None:
    findings = [f for f in SecurityAnalyzer().run(_ctx(secrets)) if f.rule_id == "SEC-001"]
    assert findings, "expected SEC-001"
    top = max(findings, key=lambda f: f.occurrence_count)
    assert top.severity == "critical"
    assert top.confidence == "high"
    joined = " ".join(e.snippet or "" for e in top.evidence)
    assert "AKIAIOSFODNN7FAKEKEY" not in joined
    assert "ghp_FAKEFAKEFAKEFAKEFAKEFAKE12" not in joined
    assert "****" in joined


def test_security_sensitive_files(secrets: Path) -> None:
    findings = [f for f in SecurityAnalyzer().run(_ctx(secrets)) if f.rule_id == "SEC-002"]
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert any(e.file_path == ".env" for e in findings[0].evidence)


def test_security_insecure_patterns(tmp_path: Path) -> None:
    _write(tmp_path, "index.js", 'var x = eval("1 + 1");\n', )
    _write(tmp_path, "view.js", "el.innerHTML = userInput;\n")
    findings = [f for f in SecurityAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "SEC-003"]
    assert len(findings) == 2
    assert any("eval(" in f.title for f in findings)
    assert any("HTML" in f.title for f in findings)


def test_security_api_route_without_auth(tmp_path: Path) -> None:
    _write(tmp_path, "routes/users.js", 'router.get("/users", listUsers);\n')
    findings = [f for f in SecurityAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "SEC-005"]
    assert len(findings) == 1
    assert findings[0].confidence == "low"
    assert findings[0].group_key == "SEC-005|routes/users.js"


# ------------------------------------------------------------------------ quality

def test_quality_high_complexity(tmp_path: Path) -> None:
    lines = ["function complicated(x) {", "  let r = 0;"]
    for i in range(0, 12):
        lines.append(f"  else if (x === {i}) r = {i};")
    lines.append("  if (x < 0 && x > -100) r = -1;")
    lines.append("  if (x > 100 || x < -1000) r = 11;")
    lines.append("  return r;")
    lines.append("}")
    _write(tmp_path, "calc.js", "\n".join(lines) + "\n")

    findings = [f for f in QualityAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "QUA-001"]
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].confidence == "high"
    assert any(e.symbol == "complicated" for e in findings[0].evidence)


def test_quality_unused_imports(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "index.js",
        'import fs from "fs";\nimport path from "path";\nimport { readFileSync } from "node:fs";\nconsole.log(fs, path);\n',
    )
    findings = [f for f in QualityAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "QUA-004"]
    assert len(findings) == 1
    assert any(e.symbol == "readFileSync" for e in findings[0].evidence)


# ----------------------------------------------------------------------- testing

def test_testing_no_tests_high(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"scripts": {"start": "node index.js"}}\n')
    _write(tmp_path, "index.js", "console.log(1);\n")
    findings = [f for f in TestingAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "TST-001"]
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].confidence == "high"


def test_testing_tests_but_no_coverage(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"scripts": {"test": "node --test"}}\n')
    _write(tmp_path, "add.test.js", "const assert = require('assert');\nassert(1 === 1);\n")
    findings = [f for f in TestingAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "TST-002"]
    assert len(findings) == 1
    assert findings[0].severity == "info"


def test_testing_critical_module_without_test(tmp_path: Path) -> None:
    _write(tmp_path, "src/auth.js", "export function login() {}\n")
    _write(tmp_path, "index.js", 'import { login } from "./src/auth.js";\nconsole.log(login);\n')
    findings = [f for f in TestingAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "TST-003"]
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert any("auth" in (e.file_path or "") for e in findings[0].evidence)


def test_testing_missing_test_script(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", '{"name": "x"}\n')
    _write(tmp_path, "add.test.js", "const assert = require('assert');\nassert(true);\n")
    findings = [f for f in TestingAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "TST-004"]
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].confidence == "high"


def test_testing_clean_has_no_findings(clean_js: Path) -> None:
    findings = TestingAnalyzer().run(_ctx(clean_js))
    assert [f.rule_id for f in findings if f.severity in ("high", "medium", "critical")] == []


def test_testing_almost_no_tests_is_high(almost_no_tests: Path) -> None:
    findings = [f for f in TestingAnalyzer().run(_ctx(almost_no_tests)) if f.rule_id == "TST-001"]
    assert len(findings) == 1
    assert findings[0].severity == "high"


# ------------------------------------------------------------------- documentation

def test_documentation_readme_missing(tmp_path: Path) -> None:
    _write(tmp_path, "index.js", "console.log(1);\n")
    findings = [f for f in DocumentationAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "DOC-001"]
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].confidence == "high"


def test_documentation_undocumented_env(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# demo\n\nA tiny demo.\n")
    _write(tmp_path, "index.js", "const key = process.env.SECRET_VAR;\nconsole.log(key);\n")
    findings = [f for f in DocumentationAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "DOC-003"]
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert any(e.symbol == "SECRET_VAR" for e in findings[0].evidence)


# -------------------------------------------------------------------- architecture

def test_architecture_circular_imports(circular_deps: Path) -> None:
    findings = [f for f in ArchitectureAnalyzer().run(_ctx(circular_deps)) if f.rule_id == "ARC-001"]
    assert len(findings) == 1
    assert findings[0].confidence == "high"
    assert findings[0].group_key == "ARC-001|cycles"
    assert findings[0].occurrence_count >= 1


def test_architecture_clean_no_cycles(clean_js: Path) -> None:
    findings = [f for f in ArchitectureAnalyzer().run(_ctx(clean_js)) if f.rule_id == "ARC-001"]
    assert findings == []


# --------------------------------------------------------------------- git hygiene

def test_git_committed_artifacts(tmp_path: Path) -> None:
    _write(tmp_path, ".DS_Store", "\x00\x00\x00")
    _write(tmp_path, "index.js", "console.log(1);\n")
    _write(tmp_path, ".gitignore", "node_modules\n.env\n")
    findings = [f for f in GitHygieneAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "GIT-001"]
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert any(e.file_path == ".DS_Store" for e in findings[0].evidence)


def test_git_missing_gitignore(tmp_path: Path) -> None:
    _write(tmp_path, "index.js", "console.log(1);\n")
    findings = [f for f in GitHygieneAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "GIT-002"]
    assert len(findings) == 1
    assert findings[0].group_key == "GIT-002|missing"


def test_git_large_files(tmp_path: Path) -> None:
    _write(tmp_path, "assets/data.bin", "0" * (5 * 1024 * 1024 + 1))
    _write(tmp_path, "index.js", "console.log(1);\n")
    findings = [f for f in GitHygieneAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "GIT-003"]
    assert len(findings) == 1
    assert any(e.metric_name == "size_bytes" for e in findings[0].evidence)


# ---------------------------------------------------------------------- deployment

def test_deployment_missing_definition(tmp_path: Path) -> None:
    _write(tmp_path, "package.json", "{}")
    _write(tmp_path, "index.js", "console.log(1);\n")
    findings = [f for f in DeploymentAnalyzer().run(_ctx(tmp_path)) if f.rule_id == "DEP-LY-001"]
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].confidence == "high"


def test_deployment_dockerfile_ok(tmp_path: Path) -> None:
    _write(tmp_path, "Dockerfile", "FROM node:20\n")
    _write(tmp_path, "index.js", "console.log(1);\n")
    findings = DeploymentAnalyzer().run(_ctx(tmp_path))
    assert [f.rule_id for f in findings] == []


# -------------------------------------------------------------------- whole pipeline

def test_all_analyzers_run_without_error(clean_js: Path) -> None:
    ctx = _ctx(clean_js)
    for analyzer in (
        SecurityAnalyzer(),
        QualityAnalyzer(),
        TestingAnalyzer(),
        DocumentationAnalyzer(),
        ArchitectureAnalyzer(),
        GitHygieneAnalyzer(),
        DeploymentAnalyzer(),
    ):
        assert isinstance(analyzer.run(ctx), list)