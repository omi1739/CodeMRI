from __future__ import annotations

from pathlib import Path

from app.analyzers._shared import (
    duplicated_line_count,
    function_blocks,
    iter_source_files,
    unused_import_names,
)
from app.analyzers.base import Evidence, Finding, ScanContext

COMPLEXITY_THRESHOLD = 14
LARGE_FILE_LOC_THRESHOLD = 800
DUP_LINE_THRESHOLD = 24
_MAX_EXAMPLES = 5


class QualityAnalyzer:
    name = "quality"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        root = Path(ctx.source_dir)
        findings: list[Finding] = []
        findings.extend(self._complexity(root, ctx.inventory))
        findings.extend(self._large_files(ctx.inventory))
        findings.extend(self._duplication(root, ctx.inventory))
        findings.extend(self._unused(root, ctx.inventory))
        return findings

    # QUA-001 ------------------------------------------------------------------
    def _complexity(self, root: Path, inventory: list[dict]) -> list[Finding]:
        findings: list[Finding] = []
        for path, rel, text in iter_source_files(root, inventory):
            hot = [b for b in function_blocks(text) if b[1] >= COMPLEXITY_THRESHOLD]
            if not hot:
                continue
            hot.sort(key=lambda b: -b[1])
            evidence = [
                Evidence(
                    file_path=rel,
                    line_start=text.find(name) + 1 if name and name != "anonymous" else None,
                    symbol=name,
                    metric_name="cyclomatic_estimate",
                    metric_value=float(complexity),
                    reason="high_complexity_function",
                )
                for name, complexity, _ in hot[:_MAX_EXAMPLES]
            ]
            findings.append(
                Finding(
                    category="code_quality",
                    rule_id="QUA-001",
                    title=f"{len(hot)} high-complexity function(s) in {rel}",
                    severity="medium",
                    confidence="high",
                    description=(
                        f"{rel} contains a function with an estimated cyclomatic complexity "
                        f"of {hot[0][1]} (threshold {COMPLEXITY_THRESHOLD}). High complexity makes "
                        "code harder to read, test, and maintain."
                    ),
                    recommendation="Break the function into smaller pieces, extract branches, and add tests.",
                    analyzer=self.name,
                    group_key=f"QUA-001|{rel}",
                    occurrence_count=len(hot),
                    evidence=evidence,
                )
            )
        return findings

    # QUA-002 ------------------------------------------------------------------
    def _large_files(self, inventory: list[dict]) -> list[Finding]:
        big = [
            entry
            for entry in inventory
            if entry.get("language")
            and not entry.get("is_generated")
            and not entry.get("is_ignored")
            and int(entry.get("loc") or 0) >= LARGE_FILE_LOC_THRESHOLD
        ]
        if not big:
            return []
        return [
            Finding(
                category="code_quality",
                rule_id="QUA-002",
                title=f"{len(big)} very large source file(s)",
                severity="low",
                confidence="high",
                description=(
                    f"{len(big)} source file(s) exceed {LARGE_FILE_LOC_THRESHOLD} lines. Large "
                    "files tend to hide responsibilities and grow faster."
                ),
                recommendation="Split the largest files into cohesive modules.",
                analyzer=self.name,
                group_key="QUA-002|large-files",
                occurrence_count=len(big),
                evidence=[
                    Evidence(
                        file_path=entry["path"],
                        metric_name="loc",
                        metric_value=float(entry["loc"]),
                        reason="large_source_file",
                    )
                    for entry in sorted(big, key=lambda e: -e["loc"])[:_MAX_EXAMPLES]
                ],
            )
        ]

    # QUA-003 ------------------------------------------------------------------
    def _duplication(self, root: Path, inventory: list[dict]) -> list[Finding]:
        findings: list[Finding] = []
        for path, rel, text in iter_source_files(root, inventory):
            dup_lines = duplicated_line_count(text)
            if dup_lines < DUP_LINE_THRESHOLD:
                continue
            findings.append(
                Finding(
                    category="code_quality",
                    rule_id="QUA-003",
                    title=f"Duplicated code blocks in {rel}",
                    severity="low",
                    confidence="medium",
                    description=(
                        f"~{dup_lines} lines in {rel} repeat in near-identical blocks of 5+ lines. "
                        "Duplication multiplies maintenance cost and bug-fix effort."
                    ),
                    recommendation="Extract the repeated blocks into shared helpers and reuse them.",
                    analyzer=self.name,
                    group_key=f"QUA-003|{rel}",
                    occurrence_count=dup_lines // 5,
                    evidence=[
                        Evidence(
                            file_path=rel,
                            metric_name="duplicated_lines",
                            metric_value=float(dup_lines),
                            reason="duplicate_code_block",
                        )
                    ],
                )
            )
        return findings

    # QUA-004 ------------------------------------------------------------------
    def _unused(self, root: Path, inventory: list[dict]) -> list[Finding]:
        findings: list[Finding] = []
        for path, rel, text in iter_source_files(root, inventory):
            names = unused_import_names(text)
            if not names:
                continue
            findings.append(
                Finding(
                    category="code_quality",
                    rule_id="QUA-004",
                    title=f"Possibly unused imports in {rel}",
                    severity="low",
                    confidence="high",
                    description=(
                        f"{len(names)} import(s) are referenced only at their declaration: "
                        + ", ".join(names[:8])
                    ),
                    recommendation="Remove unused imports; they indicate drift and add bundle weight.",
                    analyzer=self.name,
                    group_key=f"QUA-004|{rel}",
                    occurrence_count=len(names),
                    evidence=[
                        Evidence(
                            file_path=rel,
                            symbol=name,
                            reason="unused_import",
                        )
                        for name in names[:_MAX_EXAMPLES]
                    ],
                )
            )
        return findings