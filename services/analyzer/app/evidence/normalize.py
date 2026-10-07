from __future__ import annotations

import hashlib
import re

from sqlalchemy.orm import Session

from app.analyzers.base import Evidence as EvidenceModel
from app.analyzers.base import Finding as FindingModel
from app.db.models import Evidence, Finding

MAX_EVIDENCE_PER_FINDING = 5

_SECRETISH_PATTERNS = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|apikey|access[_-]?token|auth[_-]?token|"
    r"private[_-]?key|client[_-]?secret)\b(\s*[:=]\s*)([\"']?)([^\s\"',;]{4,})"
)
_LONG_ENTROPY_RE = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])")


def redact(text: str | None) -> str | None:
    """Mask credential-looking values. Never store a full secret."""
    if not text:
        return text
    result = text
    for pattern in _SECRETISH_PATTERNS:
        result = pattern.sub(lambda m: m.group(0)[:4] + "*" * max(len(m.group(0)) - 4, 4), result)
    result = _ASSIGNMENT_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)[:3]}***REDACTED***", result
    )
    result = _LONG_ENTROPY_RE.sub(lambda m: m.group(0)[:4] + "***REDACTED***", result)
    return result


def fingerprint_hash(rule_id: str, file_path: str | None, symbol: str | None, reason: str) -> str:
    payload = "|".join([rule_id, file_path or "", symbol or "", reason])
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def normalize_findings(session: Session, scan_id: int, findings: list[FindingModel]) -> list[Finding]:
    """Store findings with dedupe, grouping and redaction.

    Dedupe key: rule_id + group_key/file anchor. Repeated findings increment
    occurrence_count and append (capped) evidence instead of inserting rows.
    """
    existing: dict[tuple, Finding] = {}
    for row in session.query(Finding).filter(Finding.scan_id == scan_id):
        existing[(row.rule_id, row.group_key)] = row

    stored: list[Finding] = []

    for finding in findings:
        group_key = finding.group_key or _default_group_key(finding)
        key = (finding.rule_id, group_key)
        row = existing.get(key)

        if row is None:
            row = Finding(
                scan_id=scan_id,
                category=finding.category,
                rule_id=finding.rule_id,
                title=finding.title,
                severity=finding.severity,
                confidence=finding.confidence,
                description=finding.description,
                recommendation=finding.recommendation,
                analyzer=finding.analyzer,
                group_key=group_key,
                occurrence_count=0,
                fingerprint_hash=fingerprint_hash(
                    finding.rule_id, group_key, None, _first_reason(finding)
                ),
            )
            session.add(row)
            session.flush()
            existing[key] = row

        row.occurrence_count += finding.occurrence_count
        row.description = row.description or finding.description
        row.recommendation = row.recommendation or finding.recommendation

        if len(row.evidence) < MAX_EVIDENCE_PER_FINDING:
            for item in finding.evidence[: MAX_EVIDENCE_PER_FINDING - len(row.evidence)]:
                row.evidence.append(_to_evidence_row(item))
        stored.append(row)

    session.flush()
    return stored


def _default_group_key(finding: FindingModel) -> str:
    if finding.evidence:
        first = finding.evidence[0]
        parts = [finding.rule_id, first.file_path or "", str(first.line_start or "")]
        return "|".join(parts)
    return finding.rule_id


def _first_reason(finding: FindingModel) -> str:
    return finding.evidence[0].reason if finding.evidence else finding.rule_id


def _to_evidence_row(item: EvidenceModel) -> Evidence:
    return Evidence(
        file_path=item.file_path,
        line_start=item.line_start,
        line_end=item.line_end,
        symbol=item.symbol,
        metric_name=item.metric_name,
        metric_value=item.metric_value,
        snippet=redact(item.snippet),
        reason=item.reason,
    )
