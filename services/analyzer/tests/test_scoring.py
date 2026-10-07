from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.scoring.engine import compute_scores, load_weights


def row(
    rule_id: str = "SEC-001",
    category: str = "security",
    severity: str = "high",
    confidence: str = "high",
    occurrence_count: int = 1,
    row_id: int = 1,
    title: str = "Test finding",
    description: str = "desc",
    recommendation: str = "fix it",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=row_id,
        rule_id=rule_id,
        category=category,
        severity=severity,
        confidence=confidence,
        occurrence_count=occurrence_count,
        title=title,
        description=description,
        recommendation=recommendation,
    )


def score_of(result, category: str) -> int:
    return next(c.score for c in result.categories if c.category == category)


def test_weights_load() -> None:
    cfg = load_weights()
    assert sum(cfg["category_weights"].values()) == pytest.approx(1.0)
    assert cfg["severity_points"]["critical"] == 25
    assert cfg["confidence_multiplier"]["low"] == 0.3


def test_no_findings_is_100() -> None:
    result = compute_scores([], "portfolio")
    assert result.overall == 100
    assert result.label == "Excellent"


def test_single_critical_security_penalty() -> None:
    # 25 * 1.0 = 25 -> security 75
    # portfolio mode boosts docs/tests/deployment weights, so sum(weights) = 1.14:
    # overall = (75*0.20 + 100*0.94) / 1.14 = 95.6 -> 96
    result = compute_scores([row(severity="critical")], "portfolio")
    assert score_of(result, "security") == 75
    assert result.overall == 96
    assert result.label == "Excellent"


def test_low_confidence_halves_penalty() -> None:
    # medium severity low confidence: 5 * 0.3 = 1.5 -> security 98.5 -> 99 (round)
    result = compute_scores([row(severity="medium", confidence="low")], "portfolio")
    assert score_of(result, "security") == 99


def test_info_findings_never_penalize() -> None:
    result = compute_scores(
        [row(rule_id="FP-001", category="fingerprint", severity="info", confidence="high")],
        "portfolio",
    )
    assert result.overall == 100


def test_diminishing_returns_same_rule() -> None:
    # low severity high confidence: base = 2
    # 12 occurrences: 3*2 + 7*1 + 2*0.2 = 6 + 7 + 0.4 = 13.4 -> 86.6 -> 87
    result = compute_scores([row(severity="low", occurrence_count=12)], "portfolio")
    assert score_of(result, "security") == 87


def test_production_mode_boosts_security_penalty() -> None:
    # critical in security, production mode: 25 * 1.25 = 31.25 -> 68.75 -> 69
    result = compute_scores([row(severity="critical")], "production")
    assert score_of(result, "security") == 69
    portfolio = compute_scores([row(severity="critical")], "portfolio")
    assert score_of(portfolio, "security") == 75


def test_university_mode_reweights_architecture_down() -> None:
    result = compute_scores([row(severity="critical")], "university")
    arch_weight = next(c.weight for c in result.categories if c.category == "architecture")
    assert arch_weight == pytest.approx(0.15 * 0.6)


def test_labels() -> None:
    assert compute_scores([row(severity="critical")], "portfolio").label == "Excellent"
    # security 75-? need label boundaries: craft a score of 50-ish
    rows = [row(severity="critical", occurrence_count=3, category="security")]
    # penalty: 25*3 = 75 -> security 25 -> overall = 25*.2 + 100*.8 = 85 -> Good
    result = compute_scores(rows, "portfolio")
    assert score_of(result, "security") == 25
    assert result.label == "Good"


def test_explanations_and_recommendations() -> None:
    rows = [
        row(rule_id="SEC-001", severity="critical", row_id=11),
        row(
            rule_id="DEP-003",
            category="dependencies",
            severity="medium",
            row_id=12,
            title="No lockfile committed",
        ),
    ]
    result = compute_scores(rows, "production")
    security = next(c for c in result.categories if c.category == "security")
    assert security.explanation[0]["rule_id"] == "SEC-001"
    assert security.penalty > 0

    assert result.recommendations
    assert result.recommendations[0].rank == 1
    assert len(result.recommendations) <= 5
    # critical security outranks medium dependency finding
    assert result.recommendations[0].finding_ids == ["F-11"]
    assert all(r.effort in {"S", "M", "L"} for r in result.recommendations)


def test_priority_ordering_by_effort() -> None:
    # same severity/confidence/weight but different effort: S outranks L
    rows = [
        row(rule_id="SEC-001", severity="medium", row_id=1),
        row(rule_id="DEP-002", category="dependencies", severity="medium", row_id=2),
    ]
    result = compute_scores(rows, "portfolio")
    # SEC-001 effort S, DEP-002 effort L -> security finding ranks first
    assert result.recommendations[0].finding_ids == ["F-1"]
