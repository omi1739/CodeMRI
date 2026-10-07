from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.cache import cache_get, cache_put
from app.core.config import settings

log = logging.getLogger(__name__)

NPM_CACHE_TTL = 24 * 3600
OSV_CACHE_TTL = 7 * 24 * 3600


def npm_latest_version(package: str) -> str | None:
    cached = cache_get("npm", package, ttl_s=NPM_CACHE_TTL)
    if cached:
        return cached.get("latest")

    url = f"{settings.npm_registry_base}/{package.replace('/', '%2F')}"
    try:
        response = httpx.get(
            url,
            headers={
                "Accept": "application/vnd.npm.install-v1+json",
                "User-Agent": "CodeMRI-scanner",
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        log.debug("npm_lookup_failed package=%s error=%s", package, exc)
        return None

    if response.status_code != 200:
        return None

    data = response.json()
    latest = (data.get("dist-tags") or {}).get("latest")
    if not isinstance(latest, str):
        versions = data.get("versions") or {}
        latest = max(versions, default=None, key=_version_key) if versions else None
    result = {"latest": latest} if isinstance(latest, str) else None
    if result:
        cache_put("npm", package, result)
        return latest
    return None


def _version_key(version: str) -> tuple:
    parts: list[int | str] = []
    for chunk in version.split("+")[0].split("-")[0].split("."):
        parts.append(int(chunk) if chunk.isdigit() else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])  # type: ignore[return-value]


def osv_query_batch(queries: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Query OSV for npm advisories. Returns a list aligned with `queries`.

    Each element is a list of vulnerability dicts (possibly empty).
    Failures return empty lists - never claim a vulnerability we could not verify.
    """
    if not queries:
        return []

    cache_key = "batch:" + "|".join(
        f"{q['package']['name']}@{q.get('version', '')}" for q in sorted(
            queries, key=lambda q: q["package"]["name"]
        )
    )
    cached = cache_get("osv", cache_key, ttl_s=OSV_CACHE_TTL)
    if cached is not None:
        return cached

    ordered_names = [q["package"]["name"] for q in queries]
    sorted_queries = sorted(queries, key=lambda q: q["package"]["name"])
    results: list[list[dict[str, Any]] | None] = [None] * len(sorted_queries)

    try:
        response = httpx.post(
            f"{settings.osv_api_base}/v1/querybatch",
            json={"queries": sorted_queries},
            timeout=30.0,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("osv_query_failed error=%s", exc)
        return [[] for _ in queries]

    for index, result in enumerate(body.get("results", [])):
        vulns = result.get("vulns") or []
        results[index] = [_normalize_vuln(v) for v in vulns]

    by_name: dict[str, list[dict[str, Any]]] = {}
    for name, vulns in zip(ordered_names, results):
        by_name.setdefault(name, []).extend(vulns or [])

    aligned = [by_name.get(name, []) for name in ordered_names]
    cache_put("osv", cache_key, aligned)
    return aligned


def _normalize_vuln(vuln: dict[str, Any]) -> dict[str, Any]:
    aliases = vuln.get("aliases") or []
    ghsa = next((a for a in aliases if a.startswith("GHSA-")), None)
    severity_text = (vuln.get("database_specific") or {}).get("severity")
    cvss_score = None
    for item in vuln.get("severity") or []:
        if item.get("type") == "CVSS_V3" and item.get("score"):
            cvss_score = _cvss_base_score(item["score"])
    return {
        "id": vuln.get("id"),
        "ghsa": ghsa,
        "aliases": aliases,
        "summary": (vuln.get("summary") or "")[:300],
        "severity_text": severity_text,
        "cvss_score": cvss_score,
        "references": [r.get("url") for r in vuln.get("references") or [] if r.get("url")][:3],
    }


def _cvss_base_score(vector: str) -> float | None:
    """Extract the numeric base score from a CVSS vector or plain score string."""
    try:
        return float(vector)
    except ValueError:
        pass
    # CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H -> score is not embedded;
    # without a calculator we rely on database_specific.severity instead.
    return None


def severity_from_osv(vuln: dict[str, Any]) -> str:
    score = vuln.get("cvss_score")
    if isinstance(score, (int, float)):
        if score >= 9.0:
            return "critical"
        if score >= 7.0:
            return "high"
        if score >= 4.0:
            return "medium"
        return "low"
    text = (vuln.get("severity_text") or "").upper()
    for token, level in (
        ("CRITICAL", "critical"),
        ("HIGH", "high"),
        ("MODERATE", "medium"),
        ("MEDIUM", "medium"),
        ("LOW", "low"),
    ):
        if token in text:
            return level
    return "medium"
