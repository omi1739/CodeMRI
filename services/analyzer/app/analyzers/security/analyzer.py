from __future__ import annotations

import re
from pathlib import Path

from app.analyzers._shared import iter_source_files
from app.analyzers.base import Evidence, Finding, ScanContext

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

SENSITIVE_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    ".pypirc",
    ".npmrc",
    ".htpasswd",
}

_KNOWN_SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "critical"),
    ("GitHub personal token", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "critical"),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "critical"),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "critical"),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "high"),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "high"),
    ("Stripe key", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"), "critical"),
    ("Private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "critical"),
]

_ASSIGNMENT_RE = re.compile(
    r"""(?i)\b(password|passwd|secret|api[_-]?key|apikey|access[_-]?token|auth[_-]?token|"""
    r"""private[_-]?key|client[_-]?secret|secret[_-]?key)\b\s*[:=]\s*["']?([^"'#\s,;]{6,})"""
)

_EVAL_RE = re.compile(r"\beval\s*\(")
_INNER_HTML_RE = re.compile(r"\.?innerHTML\s*=|dangerouslySetInnerHTML")
_SQL_CONCAT_RE = re.compile(
    r"""(?i)(SELECT|INSERT|UPDATE|DELETE|DROP)\b[^'\"]*['\"]]?\s*\+|['\"]\s*\+|\$\{[\w.]+\}\s*['\"]""",
)
_DYNAMIC_QUERY_RE = re.compile(r"(?i)\b(db|client|pool|knex|sequelize)\w*\.(query|exec|raw)\s*\(\s*['\"`]\s*(SELECT|INSERT|UPDATE|DELETE|DROP)")

_CORS_WILDCARD_RE = re.compile(r"""(?i)origin\s*[:=]\s*["']\*["']|access-control-allow-origin\s*:\s*\*""")
_TLS_DISABLE_RE = re.compile(r"""(?i)NODE_TLS_REJECT_UNAUTHORIZED\s*[:=]\s*["']?0["']?""")
_DEBUG_ON_RE = re.compile(r"""(?i)\bdebug\s*[:=]\s*true\b""")
_HARDCODED_JWT_RE = re.compile(r"""(?i)\bjwt(secret|sign|verify)\b[^;\n]*[:=][^;\n]*["'][A-Za-z0-9_\-\.]{8,}["']""")

_API_ROUTE_RE = re.compile(r"\b(?:app|router|server|api)\.(get|post|put|patch|delete)\(\s*['\"`]?/")
_AUTH_MARKER_RE = re.compile(r"(?i)\b(auth|authenticate|session|middleware|verify|api[_-]?key|bearer|token)\b")

_MAX_EVAL_SUMMARY = 5


class SecurityAnalyzer:
    name = "security"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        root = Path(ctx.source_dir)
        findings: list[Finding] = []
        findings.extend(self._secret_scan(root, ctx.inventory))
        findings.extend(self._sensitive_files(ctx))
        findings.extend(self._insecure_patterns(root, ctx.inventory))
        findings.extend(self._insecure_config(root, ctx.inventory))
        findings.extend(self._api_auth_scan(root, ctx.inventory))
        return findings

    # SEC-001 ------------------------------------------------------------------
    def _secret_scan(self, root: Path, inventory: list[dict]) -> list[Finding]:
        findings: list[Finding] = []
        for path, rel, text in iter_source_files(root, inventory):
            hits: list[tuple[str, int, str, str]] = []
            for name, pattern, severity in _KNOWN_SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    line = text[: match.start()].count("\n") + 1
                    hits.append((name, line, severity, match.group(0)[:4] + "****"))
            for assignment in _ASSIGNMENT_RE.finditer(text):
                key, value = assignment.groups()
                line = text[: assignment.start()].count("\n") + 1
                hits.append((f"credential {key}", line, "medium", value[:4] + "****"))

            if not hits:
                continue

            severity = min((h[2] for h in hits), key=lambda s: SEVERITY_ORDER[s])
            confidence = "high" if any(h[2] == "critical" for h in hits) else "medium"
            evidence = [
                Evidence(
                    file_path=rel,
                    line_start=line,
                    symbol=name,
                    reason="secret_pattern",
                    snippet=f"{name}: {preview}",
                )
                for name, line, _, preview in hits[:5]
            ]
            findings.append(
                Finding(
                    category="security",
                    rule_id="SEC-001",
                    title=f"Probable secret or credential in {rel}",
                    severity=severity,
                    confidence=confidence,
                    description=(
                        f"{len(hits)} possible secret(s) found in {rel}. Values are masked; "
                        "verify whether these are real credentials, then rotate any that are."
                    ),
                    recommendation=(
                        "Rotate any confirmed credential, remove it from the repository, and add "
                        "the file to .gitignore. For local config, prefer environment variables."
                    ),
                    analyzer=self.name,
                    group_key=f"SEC-001|{rel}",
                    occurrence_count=len(hits),
                    evidence=evidence,
                )
            )
        return findings

    # SEC-002 ------------------------------------------------------------------
    def _sensitive_files(self, ctx: ScanContext) -> list[Finding]:
        sensitive = [
            entry["path"]
            for entry in ctx.inventory
            if entry.get("path") and _is_sensitive_path(entry["path"])
        ]
        if not sensitive:
            return []
        return [
            Finding(
                category="security",
                rule_id="SEC-002",
                title=f"{len(sensitive)} sensitive file(s) committed",
                severity="high",
                confidence="high",
                description=(
                    "These files commonly contain credentials or environment secrets and should "
                    "not be committed: " + ", ".join(sensitive[:5])
                ),
                recommendation=(
                    "Check whether these files contain secrets. If so, remove them from git "
                    "history, rotate any exposed credentials, and add them to .gitignore."
                ),
                analyzer=self.name,
                group_key="SEC-002|sensitive-files",
                occurrence_count=len(sensitive),
                evidence=[
                    Evidence(file_path=path, reason="sensitive_file_committed")
                    for path in sensitive[:5]
                ],
            )
        ]

    # SEC-003 ------------------------------------------------------------------
    def _insecure_patterns(self, root: Path, inventory: list[dict]) -> list[Finding]:
        patterns = [
            ("eval() usage", _EVAL_RE, "high"),
            ("unsafe HTML insertion", _INNER_HTML_RE, "medium"),
            ("dynamic SQL / string-concatenated query", _SQL_CONCAT_RE, "medium"),
            ("raw database query with concatenation", _DYNAMIC_QUERY_RE, "medium"),
        ]
        findings: list[Finding] = []
        for path, rel, text in iter_source_files(root, inventory):
            for label, pattern, severity in patterns:
                matches = list(pattern.finditer(text))
                if not matches:
                    continue
                evidence = [
                    Evidence(
                        file_path=rel,
                        line_start=text[: m.start()].count("\n") + 1,
                        reason=f"insecure_pattern:{label}",
                        snippet=_safe_snippet(m.group(0)),
                    )
                    for m in matches[:5]
                ]
                findings.append(
                    Finding(
                        category="security",
                        rule_id="SEC-003",
                        title=f"{label} in {rel}",
                        severity=severity,
                        confidence="medium",
                        description=(
                            f"{len(matches)} instance(s) of a pattern associated with injection "
                            f"or XSS risk found in {rel}. Review usage before shipping."
                        ),
                        recommendation="Sanitize/parameterize input; avoid eval(); use safe HTML APIs.",
                        analyzer=self.name,
                        group_key=f"SEC-003|{label}|{rel}",
                        occurrence_count=len(matches),
                        evidence=evidence,
                    )
                )
        return findings

    # SEC-004 ------------------------------------------------------------------
    def _insecure_config(self, root: Path, inventory: list[dict]) -> list[Finding]:
        checks = [
            ("CORS wildcard", _CORS_WILDCARD_RE, "medium"),
            ("TLS verification disabled", _TLS_DISABLE_RE, "medium"),
            ("debug mode enabled", _DEBUG_ON_RE, "low"),
            ("hardcoded JWT secret", _HARDCODED_JWT_RE, "high"),
        ]
        findings: list[Finding] = []
        for path, rel, text in iter_source_files(root, inventory):
            for label, pattern, severity in checks:
                matches = list(pattern.finditer(text))
                if not matches:
                    continue
                evidence = [
                    Evidence(
                        file_path=rel,
                        line_start=text[: m.start()].count("\n") + 1,
                        reason=f"insecure_config:{label}",
                        snippet=_safe_snippet(m.group(0)),
                    )
                    for m in matches[:5]
                ]
                findings.append(
                    Finding(
                        category="security",
                        rule_id="SEC-004",
                        title=f"{label} configuration detected in {rel}",
                        severity=severity,
                        confidence="medium",
                        description=(
                            f"{label} appears {len(matches)} time(s) in {rel}. This weakens "
                            "security posture if it reaches production."
                        ),
                        recommendation="Tighten configuration: explicit origins, enforce TLS, disable debug, inject secrets.",
                        analyzer=self.name,
                        group_key=f"SEC-004|{label}|{rel}",
                        occurrence_count=len(matches),
                        evidence=evidence,
                    )
                )
        return findings

    # SEC-005 ------------------------------------------------------------------
    def _api_auth_scan(self, root: Path, inventory: list[dict]) -> list[Finding]:
        findings: list[Finding] = []
        for path, rel, text in iter_source_files(root, inventory):
            if not _looks_like_api_module(rel, text):
                continue
            if _AUTH_MARKER_RE.search(text):
                continue
            findings.append(
                Finding(
                    category="security",
                    rule_id="SEC-005",
                    title=f"API routes without visible auth check: {rel}",
                    severity="medium",
                    confidence="low",
                    description=(
                        f"{rel} defines HTTP routes but contains no obvious auth, session, or "
                        "token reference in the same file. Auth may live in middleware, a "
                        "gateway, or an external service, so this is a low-confidence signal."
                    ),
                    recommendation="Confirm every endpoint is protected; centralize auth in middleware if it is not already.",
                    analyzer=self.name,
                    group_key=f"SEC-005|{rel}",
                    evidence=[
                        Evidence(
                            file_path=rel,
                            line_start=1,
                            reason="route_without_auth_marker",
                        )
                    ],
                )
            )
        return findings


def _is_sensitive_path(rel: str) -> bool:
    lowered = rel.lower()
    base = lowered.rsplit("/", 1)[-1] if "/" in lowered else lowered
    if base in SENSITIVE_FILES:
        return True
    if lowered.endswith((".pem", ".key", ".p12", ".p8", ".pfx")):
        return True
    if "credential" in lowered and lowered.endswith(".json"):
        return True
    if "service-account" in lowered and lowered.endswith(".json"):
        return True
    if "id_rsa" in base or "id_ed25519" in base or "id_ecdsa" in base:
        return True
    return False


def _looks_like_api_module(rel: str, text: str) -> bool:
    lowered = rel.lower()
    if not any(seg in lowered for seg in ("routes", "controllers", "api", "handlers", "endpoints")):
        return False
    return bool(_API_ROUTE_RE.search(text))


def _safe_snippet(chunk: str) -> str:
    chunk = chunk.strip()
    return chunk[:240] + ("..." if len(chunk) > 240 else "")