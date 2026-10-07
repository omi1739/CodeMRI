from __future__ import annotations

import posixpath
from pathlib import Path

from app.analyzers._shared import locate_package_json
from app.analyzers.base import Evidence, Finding, ScanContext

CRITICAL_MODULE_HINTS = ("auth", "payment", "billing", "account", "session", "token")
COVERAGE_MARKERS = ("coverage", "lcov", "nyc", "c8", "coveralls", "codecov", "istanbul")
TEST_SCRIPT_REQUIRED_FRAMEWORKS = ()

MAX_CRITICAL_EXAMPLES = 5


class TestingAnalyzer:
    name = "testing"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        root = Path(ctx.source_dir)
        inventory = ctx.inventory or []
        _, package = locate_package_json(root)
        findings: list[Finding] = []
        findings.extend(self._missing_tests(ctx, root, inventory, package))
        findings.extend(self._missing_test_script(package, inventory))
        findings.extend(self._uncovered_critical_modules(root, inventory))
        return findings

    # TST-001 + TST-002 ---------------------------------------------------------
    def _missing_tests(self, ctx: ScanContext, root: Path, inventory: list[dict], package: dict) -> list[Finding]:
        test_files = [e for e in inventory if e.get("is_test")]
        test_frameworks = ctx.fingerprint.get("test_frameworks", []) if ctx.fingerprint else []
        scripts = package.get("scripts", {}) if package else {}

        if not test_files and not test_frameworks and "test" not in scripts:
            return [
                Finding(
                    category="testing",
                    rule_id="TST-001",
                    title="No tests detected",
                    severity="high",
                    confidence="high",
                    description=(
                        "No test files, test framework, or 'test' script was found. Without "
                        "automated tests, regressions go undetected."
                    ),
                    recommendation="Add a test framework and cover the core behaviors with a few tests.",
                    analyzer=self.name,
                    group_key="TST-001|none",
                    evidence=[Evidence(file_path="package.json", reason="no_tests_detected")],
                )
            ]

        coverage_evidence = _coverage_artifacts(root, inventory, scripts) if test_files else []
        if test_files and not coverage_evidence:
            return [
                Finding(
                    category="testing",
                    rule_id="TST-002",
                    title="Tests exist but coverage is unknown",
                    severity="info",
                    confidence="high",
                    description=(
                        f"{len(test_files)} test file(s) were detected, but no committed coverage "
                        "artifact or coverage script is present, so we cannot assess how much of "
                        "the code is exercised."
                    ),
                    recommendation="Run coverage locally and commit the report or upload it to a coverage service.",
                    analyzer=self.name,
                    group_key="TST-002|coverage-unknown",
                    evidence=[
                        Evidence(file_path="package.json", reason="no_coverage_artifact"),
                    ],
                )
            ]
        return []

    # TST-004 ------------------------------------------------------------------
    def _missing_test_script(self, package: dict, inventory: list[dict]) -> list[Finding]:
        test_files = [e for e in inventory if e.get("is_test")]
        if not test_files:
            return []
        if package and "test" in (package.get("scripts") or {}):
            return []
        return [
            Finding(
                category="testing",
                rule_id="TST-004",
                title="No 'test' script in package.json",
                severity="medium",
                confidence="high",
                description=(
                    f"{len(test_files)} test file(s) exist but package.json defines no 'test' "
                    "script, so running the suite is not standardized."
                ),
                recommendation="Add a 'test' script (e.g. 'jest' or 'node --test') so CI and "
                "developers run the same command.",
                analyzer=self.name,
                group_key="TST-004|no-script",
                evidence=[Evidence(file_path="package.json", reason="test_script_missing")],
            )
        ]

    # TST-003 ------------------------------------------------------------------
    def _uncovered_critical_modules(self, root: Path, inventory: list[dict]) -> list[Finding]:
        critical: list[dict] = []
        test_paths = [e["path"] for e in inventory if e.get("is_test")]

        for entry in inventory:
            rel = entry.get("path") or ""
            if not rel.lower().endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
                continue
            if entry.get("is_test") or entry.get("is_generated"):
                continue
            lowered = rel.lower()
            if not any(hint in lowered for hint in CRITICAL_MODULE_HINTS):
                continue
            if not _has_matching_test(rel, test_paths):
                critical.append(entry)

        if not critical:
            return []

        return [
            Finding(
                category="testing",
                rule_id="TST-003",
                title=f"{len(critical)} critical module(s) without an obvious test",
                severity="medium",
                confidence="medium",
                description=(
                    "Modules related to auth/payment/accounting have no matching test file in "
                    "the expected locations: "
                    + ", ".join(e["path"] for e in critical[:3])
                    + ". These are high-impact paths where regressions are most costly."
                ),
                recommendation="Add focused tests for these modules, especially error and edge cases.",
                analyzer=self.name,
                group_key="TST-003|critical-modules",
                occurrence_count=len(critical),
                evidence=[
                    Evidence(file_path=e["path"], reason="critical_module_without_test")
                    for e in critical[:MAX_CRITICAL_EXAMPLES]
                ],
            )
        ]


def _coverage_artifacts(root: Path, inventory: list[dict], scripts: dict) -> list[str]:
    for script in scripts.values():
        if isinstance(script, str) and any(m in script.lower() for m in COVERAGE_MARKERS):
            return ["via " + script]
    return [
        e["path"]
        for e in inventory
        if any(m in (e.get("path") or "").lower() for m in COVERAGE_MARKERS)
    ]


def _has_matching_test(rel: str, test_paths: list[str]) -> bool:
    base = posixpath.basename(rel)
    stem = base.split(".")[0]
    dirname = posixpath.dirname(rel)
    for ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        candidates = [
            posixpath.join(dirname, f"{stem}.test{ext}"),
            posixpath.join(dirname, f"{stem}.spec{ext}"),
            posixpath.join(dirname, f"__tests__", f"{stem}.test{ext}"),
            posixpath.join(dirname, f"__tests__", f"{stem}.spec{ext}"),
            posixpath.join("tests", dirname, f"{stem}.test{ext}"),
            posixpath.join("test", dirname, f"{stem}.test{ext}"),
            posixpath.join("tests", dirname, f"{stem}.spec{ext}"),
            posixpath.join("test", dirname, f"{stem}.spec{ext}"),
        ]
        for candidate in candidates:
            if candidate in test_paths or f"/{candidate}" in test_paths:
                return True
    return False