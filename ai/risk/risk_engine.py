"""
Deterministic, transparent risk scoring for a single habitation.

Design rule from the project guide, followed literally here: explainability
beats accuracy. Every number this module produces must be traceable back to
config/weights.py - there is no hidden logic, no trained model, and no
factor that isn't named in RISK_WEIGHTS.

Pure function design: calculate_risk() takes a typed HabitationEvidence in
and returns a typed RiskResult out. No global state, no file I/O, no
network calls inside this module - that is what makes it trivially unit
testable and safe to call from pipeline.py without surprises.
"""

from __future__ import annotations

from ai.config.weights import (
    HISTORICAL_EVENTS_MAX,
    HISTORICAL_EVENTS_MIN,
    POPULATION_MAX,
    POPULATION_MIN,
    RISK_WEIGHTS,
)
from ai.schemas.contracts import HabitationEvidence, RiskBreakdown, RiskResult


def _min_max_scale(value: float, lo: float, hi: float) -> float:
    """Scale value into 0-100, clamped at the boundaries (capped, not
    extrapolated) so an unusually large input can't push a factor above 100
    or below 0 and silently distort the weighted total."""
    if hi <= lo:
        raise ValueError(f"Invalid normalization range: lo={lo}, hi={hi}")
    scaled = (value - lo) / (hi - lo) * 100
    return max(0.0, min(100.0, scaled))


def _risk_level_for(risk_score: float) -> str:
    """Maps a 0-100 score to a human-readable band. Thresholds here are
    purely descriptive labels for risk_score - the actual relocation
    decision thresholds live separately in priority_engine.py, on purpose,
    since "how bad is it" and "how urgently must we act" are different
    questions with different inputs."""
    if risk_score >= 75:
        return "CRITICAL"
    if risk_score >= 50:
        return "HIGH"
    if risk_score >= 25:
        return "MODERATE"
    return "LOW"


def calculate_risk(evidence: HabitationEvidence) -> RiskResult:
    """Compute the weighted risk score and full per-factor breakdown for
    one habitation. Never guesses a missing value - HabitationEvidence
    validation already guarantees every field here is present and in range
    before this function is ever called."""

    hazard_component = evidence.hazard_exposure * 100
    population_component = _min_max_scale(
        evidence.population, POPULATION_MIN, POPULATION_MAX
    )
    vulnerability_component = evidence.vulnerability * 100
    historical_component = _min_max_scale(
        evidence.historical_events, HISTORICAL_EVENTS_MIN, HISTORICAL_EVENTS_MAX
    )
    # Poor road access should INCREASE risk, so we invert: a road_accessibility
    # of 1.0 (excellent) contributes 0 risk; 0.0 (no road) contributes full 100.
    road_component = (1 - evidence.road_accessibility) * 100

    hazard_contribution = hazard_component * RISK_WEIGHTS["hazard_exposure"]
    population_contribution = population_component * RISK_WEIGHTS["population"]
    vulnerability_contribution = vulnerability_component * RISK_WEIGHTS["vulnerability"]
    historical_contribution = historical_component * RISK_WEIGHTS["historical_events"]
    road_contribution = road_component * RISK_WEIGHTS["road_accessibility"]

    risk_score = (
        hazard_contribution
        + population_contribution
        + vulnerability_contribution
        + historical_contribution
        + road_contribution
    )
    risk_score = round(risk_score, 1)

    breakdown = RiskBreakdown(
        hazard_exposure_contribution=round(hazard_contribution, 1),
        population_contribution=round(population_contribution, 1),
        vulnerability_contribution=round(vulnerability_contribution, 1),
        historical_contribution=round(historical_contribution, 1),
        road_contribution=round(road_contribution, 1),
    )

    explanation = (
        f"{evidence.name} ({evidence.habitation_id}) scored {risk_score}/100: "
        f"hazard exposure {evidence.hazard_exposure * 100:.0f}% contributed "
        f"{breakdown.hazard_exposure_contribution}, population "
        f"{evidence.population} contributed {breakdown.population_contribution}, "
        f"vulnerability {evidence.vulnerability * 100:.0f}% contributed "
        f"{breakdown.vulnerability_contribution}, {evidence.historical_events} "
        f"historical events contributed {breakdown.historical_contribution}, "
        f"road accessibility {evidence.road_accessibility:.2f} contributed "
        f"{breakdown.road_contribution}."
    )

    return RiskResult(
        habitation_id=evidence.habitation_id,
        risk_score=risk_score,
        risk_level=_risk_level_for(risk_score),
        risk_breakdown=breakdown,
        explanation=explanation,
    )