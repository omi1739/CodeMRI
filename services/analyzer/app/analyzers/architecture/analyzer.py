from __future__ import annotations

import posixpath
from pathlib import Path

from app.analyzers._shared import (
    is_entry_path,
    file_complexity_estimate,
    import_specifiers,
    is_local_specifier,
    resolve_relative_import,
)
from app.analyzers.base import Evidence, Finding, ScanContext

GOD_MODULE_IN_DEGREE = 8
MAX_PATHS = 6


class ArchitectureAnalyzer:
    name = "architecture"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        root = Path(ctx.source_dir)
        graph, file_set = figure_inventory(root, ctx.inventory)
        alias_specs = _collect_non_local_specifiers(root, ctx.inventory)
        findings: list[Finding] = []
        findings.extend(self._circular(graph))
        findings.extend(self._god_modules(graph))
        findings.extend(self._orphans(graph, file_set, alias_specs))
        findings.extend(self._high_risk(graph, file_set, root, ctx.inventory))
        return findings

    # ARC-001 ------------------------------------------------------------------
    def _circular(self, graph: dict[str, set[str]]) -> list[Finding]:
        cycles = _find_cycles(graph)
        if not cycles:
            return []
        return [
            Finding(
                category="architecture",
                rule_id="ARC-001",
                title=f"{len(cycles)} circular import schema(s)",
                severity="medium",
                confidence="high",
                description=_describe_cycles(cycles),
                recommendation=(
                    "Break the cycle by extracting the shared logic into a new module that both "
                    "files import."
                ),
                analyzer=self.name,
                group_key="ARC-001|cycles",
                occurrence_count=len(cycles),
                evidence=[
                    Evidence(
                        file_path=" / -> ".join(path[:3]),
                        reason="circular_import",
                        snippet=" -> ".join(path[:3]),
                    )
                    for path in cycles[:MAX_PATHS]
                ],
            )
        ]

    # ARC-002 ------------------------------------------------------------------
    def _god_modules(self, graph: dict[str, set[str]]) -> list[Finding]:
        importers = _count_importers(graph)
        gods = sorted(
            ((module, degree) for module, degree in importers.items() if degree >= GOD_MODULE_IN_DEGREE),
            key=lambda item: -item[1],
        )
        if not gods:
            return []
        return [
            Finding(
                category="architecture",
                rule_id="ARC-002",
                title=f"{len(gods)} module(s) with very high fan-in",
                severity="medium",
                confidence="medium",
                description=(
                    "These modules are imported by many others and concentrate responsibility: "
                    + ", ".join(f"{m} ({d})" for m, d in gods[:3])
                ),
                recommendation="Split the god module into focused modules by responsibility.",
                analyzer=self.name,
                group_key="ARC-002|god-modules",
                occurrence_count=len(gods),
                evidence=[
                    Evidence(file_path=module, metric_name="importers", metric_value=float(degree), reason="high_fan_in")
                    for module, degree in gods[:MAX_PATHS]
                ],
            )
        ]

    # ARC-003 ------------------------------------------------------------------
    def _orphans(self, graph: dict[str, set[str]], file_set: set[str], alias_specs: set[str]) -> list[Finding]:
        importers = _count_importers(graph)
        orphans = []
        for module in sorted(file_set):
            if module in importers:
                continue
            if is_entry_path(module):
                continue
            if module.startswith(("test", "tests", "__tests__")) or "/test" in module or "test" in module.split("/")[-1]:
                continue
            if not module.lower().endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
                continue
            if _referenced_by_alias(module, alias_specs):
                continue
            orphans.append(module)
        if not orphans:
            return []
        return [
            Finding(
                category="architecture",
                rule_id="ARC-003",
                title=f"{len(orphans)} module(s) never imported",
                severity="low",
                confidence="low",
                description=(
                    "These files are never imported by any other scanned module — possible dead "
                    "code or entrypoints we cannot see (dynamic imports, scripts, CLI): "
                    + ", ".join(orphans[:4])
                ),
                recommendation="Confirm whether each module is used; remove or document dead code.",
                analyzer=self.name,
                group_key="ARC-003|orphans",
                occurrence_count=len(orphans),
                evidence=[Evidence(file_path=m, reason="orphan_module") for m in orphans[:5]],
            )
        ]

    # MNT-001 (derived) ---------------------------------------------------------
    def _high_risk(self, graph: dict[str, set[str]], file_set: set[str], root: Path, inventory: list[dict]) -> list[Finding]:
        importers = _count_importers(graph)
        test_paths = {e["path"] for e in inventory if e.get("is_test")}
        source_texts = {rel: text for _, rel, text in _walk(root, inventory)}

        risky: list[tuple[str, int, int]] = []
        for module, degree in importers.items():
            if degree < GOD_MODULE_IN_DEGREE:
                continue
            text = source_texts.get(module)
            complexity = file_complexity_estimate(text) if text else 0
            if complexity < 10:
                continue
            if _has_test_for(module, test_paths):
                continue
            risky.append((module, degree, complexity))

        if not risky:
            return []

        return [
            Finding(
                category="maintainability",
                rule_id="MNT-001",
                title=f"{len(risky)} high-risk module(s) (high fan-in + complexity, untested)",
                severity="medium",
                confidence="medium",
                description=(
                    "Combining import fan-in, complexity and missing tests, these modules carry "
                    "outsized regression risk: "
                    + ", ".join(f"{m} ({d} importers)" for m, d, _ in risky[:3])
                ),
                recommendation="Add tests for these modules first, then consider refactoring them.",
                analyzer=self.name,
                group_key="MNT-001|high-risk",
                occurrence_count=len(risky),
                evidence=[
                    Evidence(
                        file_path=m,
                        metric_name="importers",
                        metric_value=float(d),
                        reason="high_risk_module",
                    )
                    for m, d, _ in risky[:5]
                ],
            )
        ]


def figure_inventory(root: Path, inventory: list[dict]) -> tuple[dict[str, set[str]], set[str]]:
    file_set = {e["path"] for e in inventory}
    graph: dict[str, set[str]] = {}
    for _, rel, text in _walk(root, inventory):
        targets: set[str] = set()
        for spec in import_specifiers(text):
            if not is_local_specifier(spec):
                continue
            resolved = resolve_relative_import(rel, spec, file_set)
            if resolved and resolved != rel:
                targets.add(resolved)
        if targets:
            graph[rel] = targets
    return graph, file_set


def _count_importers(graph: dict[str, set[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for targets in graph.values():
        for target in targets:
            counts[target] = counts.get(target, 0) + 1
    return counts


def _walk(root: Path, inventory: list[dict]):
    from app.analyzers._shared import iter_source_files

    return list(iter_source_files(root, inventory))


def _collect_non_local_specifiers(root: Path, inventory: list[dict]) -> set[str]:
    """Import specifiers that are not relative — e.g. `@/app/components/ui`,
    `~components/Button` — which relative resolution cannot see."""
    specs: set[str] = set()
    for _, _, text in _walk(root, inventory):
        for spec in import_specifiers(text):
            if not is_local_specifier(spec):
                specs.add(spec.strip())
    return specs


def _referenced_by_alias(module: str, alias_specs: set[str]) -> bool:
    """Best-effort check that some aliased import points at `module`.

    Path segments aren't guaranteed to resolve exactly (tsconfigs vary), so match
    on the module's basename or on its repo-relative tail appearing in the spec.
    """
    stem = posixpath.splitext(module)[0]
    base = posixpath.basename(stem)
    for spec in alias_specs:
        clean = spec.strip().strip("'\"")
        tail = clean.split("/")[-1].split(".")[0]
        if tail == base:
            return True
        if stem.endswith(clean.lstrip("/@~")):
            return True
    return False


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph.get(node, ()):
            if nxt not in color:
                visit(nxt)
            elif color[nxt] == GRAY:
                try:
                    start = stack.index(nxt)
                except ValueError:
                    continue
                cycle = tuple(stack[start:] + [nxt])
                cycles.add(cycle)
        stack.pop()
        color[node] = BLACK

    for node in sorted(graph):
        if node not in color:
            visit(node)
    return [list(c) for c in sorted(cycles, key=lambda c: (len(c), c))]


def _describe_cycles(cycles: list[list[str]]) -> str:
    parts = [f"{len(c)} modules: " + " -> ".join(c[:3]) for c in cycles[:3]]
    return "Circular imports mean initialization order can break and coupling grows: " + "; ".join(parts)


def _has_test_for(module: str, test_paths: set[str]) -> bool:
    import posixpath

    base = posixpath.basename(module)
    stem = base.split(".")[0]
    dirname = posixpath.dirname(module)
    for candidate in (
        posixpath.join(dirname, f"{stem}.test.js"),
        posixpath.join(dirname, f"{stem}.test.ts"),
        posixpath.join(dirname, f"{stem}.spec.js"),
        posixpath.join(dirname, f"{stem}.spec.ts"),
        posixpath.join("tests", dirname, f"{stem}.test.js"),
        posixpath.join("test", dirname, f"{stem}.test.js"),
    ):
        if candidate in test_paths:
            return True
    return False