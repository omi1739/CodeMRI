from __future__ import annotations

import re
from pathlib import Path

from app.analyzers._shared import iter_source_files
from app.analyzers.base import Evidence, Finding, ScanContext

README_HINTS = ("readme",)
README_BREAKING_EMPTY = 60
SETUP_HEADINGS = ("install", "getting started", "getting-started", "setup", "quick start", "prerequis", "usage", "run", "start")
ENV_USAGE_RE = re.compile(r"process\.env\.([A-Z][A-Z0-9_]{1,64})|process\.env\[\s*['\"]([A-Za-z0-9_]+)['\"]\s*\]")
CLAIM_KEYWORDS = (
    ("GraphQL", "graphql"),
    ("WebSocket", ("websocket", "ws://", "socket.io")),
    ("Docker", "docker"),
    ("Redis", ("redis", "ioredis")),
    ("PostgreSQL", ("postgres", "pg")),
    ("OAuth", ("oauth", "passport")),
    ("Webhooks", "webhook"),
    ("Rate limiting", ("rate.limit", "ratelimit", "express-rate-limit")),
    ("i18n", ("i18next", "react-intl")),
    ("Background jobs", ("bull", "queue", "celery", "sidekiq")),
)


class DocumentationAnalyzer:
    name = "documentation"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        root = Path(ctx.source_dir)
        inventory = ctx.inventory or []
        findings: list[Finding] = []
        findings.extend(self._readme_quality(root, inventory))
        findings.extend(self._env_docs(root, inventory))
        findings.extend(self._claims(req=root, inventory=inventory))
        return findings

    # DOC-001 / DOC-002 ---------------------------------------------------------
    def _readme_quality(self, root: Path, inventory: list[dict]) -> list[Finding]:
        readme_path = _find_readme(root)
        if readme_path is None:
            return [
                Finding(
                    category="documentation",
                    rule_id="DOC-001",
                    title="README missing",
                    severity="medium",
                    confidence="high",
                    description=(
                        "No README file was found at the repository root. A README is the first "
                        "thing collaborators and users see; its absence hurts onboarding."
                    ),
                    recommendation="Add a README with the project's purpose, setup steps, and usage.",
                    analyzer=self.name,
                    group_key="DOC-001|missing",
                    evidence=[Evidence(file_path="README.md", reason="readme_missing")],
                )
            ]

        try:
            text = readme_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [self._empty_readme(readme_path)]

        words = len(re.findall(r"\w+", text))
        if words < README_BREAKING_EMPTY:
            return [self._empty_readme(readme_path)]

        headings = [h.strip().lower() for h in re.findall(r"(?m)^#+\s+(.*)$", text)]
        if not any(_heading_matches(heading, SETUP_HEADINGS) for heading in headings):
            return [
                Finding(
                    category="documentation",
                    rule_id="DOC-002",
                    title="No setup / install instructions in README",
                    severity="medium",
                    confidence="medium",
                    description=(
                        "The README does not contain obvious install/setup/usage headings, so "
                        "new contributors may not know how to run the project."
                    ),
                    recommendation="Add an 'Install' section with the commands to get the project running.",
                    analyzer=self.name,
                    group_key="DOC-002|no-setup",
                    evidence=[
                        Evidence(
                            file_path=readme_path.name,
                            reason="no_setup_instructions",
                        )
                    ],
                )
            ]
        return []

    def _empty_readme(self, path: Path) -> Finding:
        return Finding(
            category="documentation",
            rule_id="DOC-001",
            title="README nearly empty",
            severity="medium",
            confidence="high",
            description="A README exists but contains very little content.",
            recommendation="Expand the README with purpose, setup, usage, and license.",
            analyzer=self.name,
            group_key="DOC-001|empty",
            evidence=[Evidence(file_path=path.name, reason="readme_nearly_empty")],
        )

    # DOC-003 ------------------------------------------------------------------
    def _env_docs(self, root: Path, inventory: list[dict]) -> list[Finding]:
        readme_text = _read_readme_text(root)
        env_example = _read_env_example(root)

        used: set[str] = set()
        for path, rel, text in iter_source_files(root, inventory):
            for first, second in ENV_USAGE_RE.findall(text):
                name = first or second
                if name:
                    used.add(name)

        if not used:
            return []

        documented: set[str] = set(env_example)
        documented |= _names_in_text(readme_text)
        undocumented = sorted(name for name in used if name not in documented)
        if not undocumented:
            return []

        return [
            Finding(
                category="documentation",
                rule_id="DOC-003",
                title=f"{len(undocumented)} environment variable(s) not documented",
                severity="medium",
                confidence="medium",
                description=(
                    "These environment variables are read in the code but not mentioned in the "
                    "README or an .env.example: " + ", ".join(undocumented[:6])
                ),
                recommendation="Document each variable and provide an .env.example with safe placeholders.",
                analyzer=self.name,
                group_key="DOC-003|env-vars",
                occurrence_count=len(undocumented),
                evidence=[
                    Evidence(
                        file_path=".env.example",
                        symbol=name,
                        reason="env_var_undocumented",
                    )
                    for name in undocumented[:5]
                ],
            )
        ]

    # DOC-004 ------------------------------------------------------------------
    def _claims(self, req: Path, inventory: list[dict]) -> list[Finding]:
        """Only ever 'no evidence found' style, low confidence, one grouped finding."""
        readme_text = _read_readme_text(req)
        if not readme_text:
            return []

        code_lower = " ".join(
            text.lower() for _, _, text in iter_source_files(req, inventory)
        )
        claims: list[str] = []
        for claim, markers in CLAIM_KEYWORDS:
            normalized_markers = markers if isinstance(markers, tuple) else (markers,)
            if not any(marker in readme_text.lower() for marker in normalized_markers):
                continue
            if not any(marker in code_lower for marker in normalized_markers):
                claims.append(claim)

        if not claims:
            return []

        return [
            Finding(
                category="documentation",
                rule_id="DOC-004",
                title="README feature claims with no supporting code",
                severity="low",
                confidence="low",
                description=(
                    "The README mentions these features, but we found no supporting dependency "
                    "or code references — 'no evidence was found' rather than a definite "
                    "contradiction: " + ", ".join(claims[:6])
                ),
                recommendation="Verify each claim; update docs to describe what the project actually does.",
                analyzer=self.name,
                group_key="DOC-004|claims",
                occurrence_count=len(claims),
                evidence=[Evidence(file_path="README.md", symbol=c, reason="readme_claim") for c in claims[:5]],
            )
        ]


def _find_readme(root: Path) -> Path | None:
    for path in root.iterdir():
        if path.is_file() and path.name.lower().startswith("readme"):
            return path
    return None


def _read_readme_text(root: Path) -> str:
    readme = _find_readme(root)
    if readme is None:
        return ""
    try:
        return readme.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_env_example(root: Path) -> list[str]:
    for name in (".env.example", ".env.sample", ".env.template"):
        path = root / name
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                return [line.split("=")[0].strip() for line in text.splitlines() if "=" in line]
            except OSError:
                return []
    return []


def _names_in_text(text: str) -> set[str]:
    names: set[str] = set()
    for first, second in ENV_USAGE_RE.findall(text):
        name = first or second
        if name:
            names.add(name)
    return names


def _heading_matches(heading: str, keywords) -> bool:
    return any(k in heading for k in keywords)