from __future__ import annotations

from pathlib import Path

from app.analyzers.base import Evidence, Finding, ScanContext

COMMITTED_ARTIFACTS = {
    ".DS_Store",
    "Thumbs.db",
    "thumbs.db",
    "desktop.ini",
    "*.log",
    "*.pyc",
    "*.class",
    "*.o",
    "*.obj",
    "*.dll",
    "*.dylib",
    "*.so",
    "node_modules/",
    "dist/",
    "build/",
    ".next/",
    "coverage/",
    ".vscode/",
    ".idea/",
    ".terraform/",
    "*.whl",
    "*.egg-info/",
    ".pytest_cache/",
}

WEAK_GITIGNORE = {".gitignore", ".git/info/exclude"}
REDUNDANT_GITIGNORE = {"*.class", "*.exe", "*.dll"}
LARGE_FILE_THRESHOLD = 5 * 1024 * 1024
_MAX_EVIDENCE = 5


class GitHygieneAnalyzer:
    name = "git_hygiene"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        root = Path(ctx.source_dir)
        findings: list[Finding] = []
        findings.extend(self._committed_artifacts(root, ctx.inventory))
        findings.extend(self._ignore_quality(root, ctx.inventory))
        findings.extend(self._large_files(ctx.inventory))
        return findings

    # GIT-001 ------------------------------------------------------------------
    def _committed_artifacts(self, root: Path, inventory: list[dict]) -> list[Finding]:
        offenders: list[dict] = []
        for entry in inventory:
            rel = entry.get("path") or ""
            if not rel or rel == ".gitignore":
                continue
            lowered = "/" + rel.lower()
            if any(_matches_artifact(lowered, pattern) for pattern in COMMITTED_ARTIFACTS):
                offenders.append(entry)
        if not offenders:
            return []

        return [
            Finding(
                category="git_hygiene",
                rule_id="GIT-001",
                title=f"{len(offenders)} build/OS artifact(s) committed",
                severity="medium",
                confidence="high",
                description=(
                    "These files are typically generated or machine-specific and should not be "
                    "in version control: "
                    + ", ".join(e["path"] for e in offenders[:4])
                ),
                recommendation="Remove them from git and add them to .gitignore.",
                analyzer=self.name,
                group_key="GIT-001|artifacts",
                occurrence_count=len(offenders),
                evidence=[
                    Evidence(file_path=e["path"], reason="committed_artifact") for e in offenders[:_MAX_EVIDENCE]
                ],
            )
        ]

    # GIT-002 ------------------------------------------------------------------
    def _ignore_quality(self, root: Path, inventory: list[dict]) -> list[Finding]:
        ignore_file = root / ".gitignore"
        if not ignore_file.is_file():
            return [
                Finding(
                    category="git_hygiene",
                    rule_id="GIT-002",
                    title="No .gitignore",
                    severity="low",
                    confidence="high",
                    description="The repository has no .gitignore, so generated or local files can be committed by accident.",
                    recommendation="Add a .gitignore covering dependencies, build output, coverage, and secrets.",
                    analyzer=self.name,
                    group_key="GIT-002|missing",
                    evidence=[Evidence(file_path=".gitignore", reason="gitignore_missing")],
                )
            ]
        text = ignore_file.read_text(encoding="utf-8", errors="replace")
        results: list[str] = []
        for pattern in (".env", "node_modules", "dist", "build", ".next", "coverage", "*.log"):
            if pattern not in text:
                results.append(pattern)
        if not results:
            return []

        return [
            Finding(
                category="git_hygiene",
                rule_id="GIT-002",
                title=".gitignore missing common entries",
                severity="low",
                confidence="medium",
                description="The .gitignore does not cover: " + ", ".join(results),
                recommendation="Add the missing entries to .gitignore.",
                analyzer=self.name,
                group_key="GIT-002|partial",
                occurrence_count=len(results),
                evidence=[
                    Evidence(file_path=".gitignore", symbol=p, reason="missing_gitignore_entry") for p in results
                ],
            )
        ]

    # GIT-003 ------------------------------------------------------------------
    def _large_files(self, inventory: list[dict]) -> list[Finding]:
        big = [
            e
            for e in inventory
            if int(e.get("size_bytes") or 0) > LARGE_FILE_THRESHOLD
            and not e.get("is_generated")
            and not e.get("is_binary", False)
        ]
        if not big:
            return []
        return [
            Finding(
                category="git_hygiene",
                rule_id="GIT-003",
                title=f"{len(big)} very large file(s) in the repository",
                severity="low",
                confidence="medium",
                description=(
                    "Files over 5 MB bloat the repository clone and history: "
                    + ", ".join(e["path"] for e in big[:3])
                ),
                recommendation="Move large assets or data out of the repo (LFS, external storage, downloads).",
                analyzer=self.name,
                group_key="GIT-003|large-files",
                occurrence_count=len(big),
                evidence=[
                    Evidence(
                        file_path=e["path"],
                        metric_name="size_bytes",
                        metric_value=float(e["size_bytes"]),
                        reason="large_file_in_repo",
                    )
                    for e in big[:_MAX_EVIDENCE]
                ],
            )
        ]


def _matches_artifact(path_with_slash: str, pattern: str) -> bool:
    pattern = pattern.lower()
    if pattern.startswith("*"):
        return path_with_slash.endswith(pattern[1:])
    if pattern.endswith("/"):
        return pattern in path_with_slash
    base = path_with_slash.rsplit("/", 1)[-1]
    return base == pattern or pattern in path_with_slash