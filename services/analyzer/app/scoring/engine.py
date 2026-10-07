from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.analyzers.base import Finding as FindingModel  # noqa: F401  (typing aid)

WEIGHTS_PATH = Path(__file__).with_name("weights.yaml")

EFFORT_POINTS = {"S": 1.0, "M": 2.0, "L": 4.0}


@dataclass
class CategoryScore:
    category: str
    score: int
    weight: float
    penalty: float
    explanation: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RecommendationOut:
    rank: int
    title: str
    explanation: str
    expected_impact: str
    effort: str
    finding_ids: list[str]
    priority: float


@dataclass
class ScoringResult:
    overall: int
    label: str
    categories: list[CategoryScore]
    recommendations: list[RecommendationOut]


@lru_cache(maxsize=1)
def load_weights() -> dict:
    with WEIGHTS_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _label_for(score: int, cfg: dict) -> str:
    for entry in cfg["labels"]:
        if score >= entry["min_score"]:
            return entry["label"]
    return "At risk"


def _occurrence_penalty(base: float, count: int, cfg: dict) -> float:
    dr = cfg["diminishing_returns"]
    full = int(dr["full_occurrences"])
    half_until = int(dr["half_until_occurrences"])
    tail = float(dr["tail_multiplier"])

    if count <= full:
        return base * count
    if count <= half_until:
        return base * full + base * 0.5 * (count - full)
    return base * full + base * 0.5 * (half_until - full) + base * tail * (count - half_until)


def _findings_like(row: Any) -> tuple[str, str, str, str, int]:
    return (row.rule_id, row.category, row.severity, row.confidence, row.occurrence_count)


def compute_scores(rows: list[Any], target_mode: str) -> ScoringResult:
    """rows: ORM Finding rows (rule_id, category, severity, confidence, occurrence_count)."""
    cfg = load_weights()
    mode = cfg["target_modes"].get(target_mode) or cfg["target_modes"]["portfolio"]
    weight_mult = mode.get("category_weight_multiplier") or {}
    sev_mult = mode.get("severity_multiplier_by_category") or {}

    severity_points = cfg["severity_points"]
    confidence_mult = cfg["confidence_multiplier"]
    base_weights = cfg["category_weights"]

    by_category: dict[str, list[Any]] = {}
    for row in rows:
        by_category.setdefault(row.category, []).append(row)

    category_scores: list[CategoryScore] = []
    effective_weights: dict[str, float] = {}

    for category, base_weight in base_weights.items():
        if base_weight <= 0:
            continue
        effective_weight = base_weight * float(weight_mult.get(category, 1.0))
        effective_weights[category] = effective_weight

        category_sev_mult = float(sev_mult.get(category, 1.0))
        penalty_total = 0.0
        explanation: list[dict[str, Any]] = []

        for row in by_category.get(category, []):
            base = severity_points.get(row.severity, 0) * confidence_mult.get(row.confidence, 0.0)
            if base == 0:
                continue
            penalty = _occurrence_penalty(base * category_sev_mult, row.occurrence_count or 1, cfg)
            if penalty <= 0:
                continue
            penalty_total += penalty
            explanation.append(
                {
                    "rule_id": row.rule_id,
                    "title": row.title,
                    "count": row.occurrence_count or 1,
                    "penalty": round(penalty, 2),
                }
            )

        explanation.sort(key=lambda item: -item["penalty"])
        score = max(0, int(100 - penalty_total + 0.5))  # round half up
        category_scores.append(
            CategoryScore(
                category=category,
                score=score,
                weight=round(effective_weight, 4),
                penalty=round(penalty_total, 2),
                explanation=explanation,
            )
        )

    total_weight = sum(effective_weights.values())
    if total_weight <= 0:
        overall = 100
    else:
        overall = round(
            sum(cs.score * effective_weights[cs.category] for cs in category_scores) / total_weight
        )
    overall = max(0, min(100, overall))

    recommendations = _rank_recommendations(rows, effective_weights, severity_points, confidence_mult, cfg)

    return ScoringResult(
        overall=overall,
        label=_label_for(overall, cfg),
        categories=category_scores,
        recommendations=recommendations,
    )


def _rank_recommendations(
    rows: list[Any],
    effective_weights: dict[str, float],
    severity_points: dict,
    confidence_mult: dict,
    cfg: dict,
) -> list[RecommendationOut]:
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        if row.category == "fingerprint":
            continue
        if severity_points.get(row.severity, 0) == 0:
            continue
        grouped.setdefault(row.rule_id, []).append(row)

    effort_by_rule = cfg.get("effort_by_rule") or {}
    default_effort = cfg.get("default_effort", "M")
    ranked: list[tuple[float, str, list[Any], str]] = []

    for rule_id, group in grouped.items():
        effort = effort_by_rule.get(rule_id, default_effort)
        effort_div = EFFORT_POINTS.get(effort, 2.0)
        best_priority = 0.0
        penalty_total = 0.0
        for row in group:
            base = severity_points.get(row.severity, 0) * confidence_mult.get(row.confidence, 0.0)
            weight = effective_weights.get(row.category, 0.0)
            priority = (base * weight) / effort_div
            best_priority = max(best_priority, priority)
            penalty_total += _occurrence_penalty(base, row.occurrence_count or 1, cfg)
        ranked.append((best_priority, rule_id, group, effort))

    ranked.sort(key=lambda item: -item[0])

    recommendations: list[RecommendationOut] = []
    for index, (priority, rule_id, group, effort) in enumerate(ranked[:5], start=1):
        representative = group[0]
        finding_ids = [f"F-{row.id}" for row in sorted(group, key=lambda r: r.id)]
        impact = min(round(max(priority * 10, 1)), 30)
        recommendations.append(
            RecommendationOut(
                rank=index,
                title=representative.title,
                explanation=(representative.description or representative.recommendation)[:600],
                expected_impact=(
                    f"Estimated +{impact} points in '{representative.category}' "
                    f"({effort} effort)"
                ),
                effort=effort,
                finding_ids=finding_ids[:20],
                priority=round(priority, 4),
            )
        )
    return recommendations
