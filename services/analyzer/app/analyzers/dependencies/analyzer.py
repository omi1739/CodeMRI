from __future__ import annotations

import re
from pathlib import Path

from app.analyzers.base import Evidence, Finding, ScanContext
from app.analyzers.dependencies.lockfile import (
    collect_dependencies,
    exact_version_from_range,
)
from app.analyzers.dependencies.net import npm_latest_version, osv_query_batch, severity_from_osv

TOOLING_MARKERS = (
    "eslint",
    "prettier",
    "babel",
    "webpack",
    "rollup",
    "jest",
    "vitest",
    "mocha",
    "cypress",
    "playwright",
    "typescript",
    "@types/",
    "@babel/",
    "postcss",
    "tailwind",
    "autoprefixer",
    "husky",
    "lint-staged",
    "commitlint",
    "nodemon",
    "rimraf",
    "cross-env",
    "concurrently",
    "npm-run-all",
    "tsup",
    "esbuild",
    "turbo",
    "stylelint",
)

_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[\w*{}\s,]+\s+from\s+)?|export\s+[\w*{}\s,]+\s+from\s+|require\()\s*['"]([^'"]+)['"]"""
)
_MAX_FILES_FOR_IMPORT_SCAN = 4000
_MAX_BYTES_FOR_IMPORT_SCAN = 512 * 1024


def _collect_import_specifiers(source_dir: Path, inventory: list[dict]) -> set[str]:
    specifiers: set[str] = set()
    scanned = 0
    for entry in inventory:
        if scanned >= _MAX_FILES_FOR_IMPORT_SCAN:
            break
        path_str = entry.get("path") or ""
        if not path_str.lower().endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte")):
            continue
        if entry.get("is_ignored") or entry.get("size_bytes", 0) > _MAX_BYTES_FOR_IMPORT_SCAN:
            continue
        path = source_dir / path_str
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        specifiers.update(_IMPORT_RE.findall(text))
    return specifiers


def _package_of(specifier: str) -> str | None:
    if specifier.startswith(".") or specifier.startswith("/") or specifier.startswith("#"):
        return None
    if specifier.startswith("@"):
        parts = specifier.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else None
    return specifier.split("/")[0]


def _is_tooling(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in TOOLING_MARKERS)


class DependencyAnalyzer:
    name = "dependencies"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        root = Path(ctx.source_dir)
        info = collect_dependencies(root)
        findings: list[Finding] = []

        findings.extend(self._lockfile_findings(info))

        if not info.declared:
            return findings

        resolved: dict[str, str] = {}
        for dep in info.declared:
            version = info.resolved.get(dep.name) or exact_version_from_range(dep.version_range)
            if version:
                resolved[dep.name] = version

        findings.extend(self._advisories(info, resolved))
        findings.extend(self._outdated(info, resolved))
        findings.extend(self._unused(ctx, root, info))
        return findings

    def _lockfile_findings(self, info) -> list[Finding]:
        findings: list[Finding] = []
        if not info.lockfiles:
            findings.append(
                Finding(
                    category="dependencies",
                    rule_id="DEP-003",
                    title="No lockfile committed",
                    severity="medium",
                    confidence="high",
                    description=(
                        "package.json exists but no lockfile (package-lock.json, yarn.lock, "
                        "pnpm-lock.yaml or bun.lockb) was found. Installs are therefore not "
                        "reproducible: different machines can resolve different versions."
                    ),
                    recommendation="Commit the lockfile for your package manager (e.g. npm install --package-lock-only).",
                    analyzer=self.name,
                    evidence=[Evidence(file_path="package.json", reason="lockfile_missing")],
                )
            )
        elif len(info.lockfiles) > 1:
            findings.append(
                Finding(
                    category="dependencies",
                    rule_id="DEP-004",
                    title="Multiple lockfiles committed",
                    severity="low",
                    confidence="high",
                    description=(
                        f"Found {len(info.lockfiles)} lockfiles: {', '.join(info.lockfiles)}. "
                        "Conflicting lockfiles cause inconsistent installs across environments."
                    ),
                    recommendation="Pick one package manager, delete the other lockfiles and document it in the README.",
                    analyzer=self.name,
                    evidence=[
                        Evidence(file_path=name, reason="lockfile_present") for name in info.lockfiles
                    ],
                )
            )
        return findings

    def _advisories(self, info, resolved: dict[str, str]) -> list[Finding]:
        if not resolved:
            return []

        queries = [
            {"package": {"ecosystem": "npm", "name": name}, "version": version}
            for name, version in sorted(resolved.items())
        ]
        results = osv_query_batch(queries)
        names = [q["package"]["name"] for q in queries]

        findings: list[Finding] = []
        for name, vulns in zip(names, results):
            if not vulns:
                continue
            version = resolved[name]
            worst = max(vulns, key=_vuln_rank)
            severity = severity_from_osv(worst)
            advisory_ids = ", ".join(
                dict.fromkeys(
                    filter(None, [v.get("ghsa") or v.get("id") for v in vulns])
                )
            )
            evidence_items = [
                Evidence(
                    file_path="package.json",
                    symbol=name,
                    metric_name="resolved_version",
                    reason="osv_advisory_exact_version_match",
                    snippet=f"{name}@{version}: {advisory_ids}",
                )
            ]
            for vuln in vulns[:4]:
                evidence_items.append(
                    Evidence(
                        file_path="package.json",
                        symbol=name,
                        reason=(vuln.get("id") or "osv").lower(),
                        snippet=f"{vuln.get('id')}: {vuln.get('summary', '')}"[:300],
                    )
                )
            findings.append(
                Finding(
                    category="dependencies",
                    rule_id="DEP-001",
                    title=f"Dependency '{name}' has a known advisory",
                    severity=severity,
                    confidence="high",
                    description=(
                        f"{name}@{version} matches {len(vulns)} advisory entry/entries in OSV "
                        f"for the exact resolved version: {advisory_ids}."
                    ),
                    recommendation=(
                        f"Upgrade {name} to a patched release, then re-run the scan. "
                        "Verify the advisory details at the linked OSV/GHSA record."
                    ),
                    analyzer=self.name,
                    group_key=f"DEP-001|{name}",
                    evidence=evidence_items,
                )
            )
        return findings

    def _outdated(self, info, resolved: dict[str, str]) -> list[Finding]:
        outdated: list[tuple[str, str, str, bool, int]] = []
        for dep in info.declared:
            current = resolved.get(dep.name) or info.resolved.get(dep.name)
            base = current or dep.version_range.lstrip("^~>=<v ")
            latest = npm_latest_version(dep.name)
            if not latest or not base:
                continue
            current_major = _major(base)
            latest_major = _major(latest)
            if current_major is None or latest_major is None:
                continue
            if latest_major > current_major:
                outdated.append((dep.name, base, latest, dep.dev, latest_major - current_major))

        if not outdated:
            return []

        outdated.sort(key=lambda item: (-item[4], item[0]))
        worst = outdated[0]
        severity = "low" if len(outdated) == 1 and worst[4] == 1 else "medium"

        evidence = [
            Evidence(
                file_path="package.json",
                symbol=name,
                metric_name="major_versions_behind",
                metric_value=float(gap),
                reason="npm_registry_latest_version",
                snippet=f"{name}: {current} -> latest {latest}" + (" (dev)" if dev else ""),
            )
            for name, current, latest, dev, gap in outdated[:5]
        ]

        return [
            Finding(
                category="dependencies",
                rule_id="DEP-002",
                title=f"{len(outdated)} dependencies outdated by one or more major versions",
                severity=severity,
                confidence="high",
                description=(
                    f"{len(outdated)} direct dependencies are behind their latest major version. "
                    f"Most behind: {worst[0]} ({worst[1]} -> {worst[2]}). "
                    "Major upgrades may include breaking changes."
                ),
                recommendation=(
                    "Upgrade incrementally, run your test suite after each batch, and check "
                    "release notes for breaking changes."
                ),
                analyzer=self.name,
                group_key="DEP-002|direct",
                occurrence_count=len(outdated),
                evidence=evidence,
            )
        ]

    def _unused(self, ctx: ScanContext, root: Path, info) -> list[Finding]:
        specifiers = _collect_import_specifiers(root, ctx.inventory)
        imported_packages = {pkg for pkg in map(_package_of, specifiers) if pkg}

        unused = [
            dep.name
            for dep in info.declared
            if not dep.dev
            and not _is_tooling(dep.name)
            and dep.name not in imported_packages
        ]
        if not unused:
            return []

        return [
            Finding(
                category="dependencies",
                rule_id="DEP-005",
                title=f"{len(unused)} possibly unused dependencies",
                severity="low",
                confidence="low",
                description=(
                    "These runtime dependencies are declared in package.json but no import or "
                    "require statement references them anywhere in the scanned source. Some "
                    "packages are used indirectly (CLI tools, plugins, peer-provided code), so "
                    "this is a weak signal only."
                ),
                recommendation="Manually verify each package before removing it.",
                analyzer=self.name,
                group_key="DEP-005|runtime",
                occurrence_count=len(unused),
                evidence=[
                    Evidence(
                        file_path="package.json",
                        symbol=name,
                        reason="declared_but_never_imported",
                    )
                    for name in sorted(unused)[:5]
                ],
            )
        ]


def _major(version: str) -> int | None:
    match = re.match(r"^v?(\d+)", version.strip())
    return int(match.group(1)) if match else None


def _vuln_rank(vuln: dict) -> int:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return order.get(severity_from_osv(vuln), 1)
