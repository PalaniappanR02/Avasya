"""
Turns a risk_score into an actionable relocation priority bucket.

Deliberately kept as a SEPARATE module from risk_engine.py: risk answers
"how dangerous is this habitation", priority answers "how urgently must we
act". They're related but not the same question, and a judge should be
able to ask about either one independently.

Pure function again: calculate_priority() takes typed inputs, returns a
typed PriorityResult, no hidden state.
"""

from __future__ import annotations

from ai.config.weights import (
    LARGE_EXPOSED_POPULATION_ESCALATION_THRESHOLD,
    PRIORITY_THRESHOLDS,
)
from ai.schemas.contracts import HabitationEvidence, PriorityResult, RiskResult


def calculate_priority(
    evidence: HabitationEvidence, risk_result: RiskResult
) -> PriorityResult:
    """Determine relocation priority from risk_score, with one documented
    escalation rule: a large absolute number of exposed people can force
    IMMEDIATE even if the normalized risk_score alone would only suggest
    SHORT_TERM. This mirrors the guide's own formula (Risk + Vulnerability +
    Exposure + Urgency -> Priority) instead of relying on risk_score alone,
    which already caps population's influence at a 20% weight and could
    under-rank a habitation with an extremely large exposed population.
    """

    reasons: list[str] = []
    risk_score = risk_result.risk_score

    if risk_score >= PRIORITY_THRESHOLDS["IMMEDIATE"]:
        priority = "IMMEDIATE"
        reasons.append(
            f"Risk score {risk_score} meets the IMMEDIATE threshold "
            f"({PRIORITY_THRESHOLDS['IMMEDIATE']}+)."
        )
    elif risk_score >= PRIORITY_THRESHOLDS["SHORT_TERM"]:
        priority = "SHORT_TERM"
        reasons.append(
            f"Risk score {risk_score} falls in the SHORT_TERM band "
            f"({PRIORITY_THRESHOLDS['SHORT_TERM']}-{PRIORITY_THRESHOLDS['IMMEDIATE'] - 1})."
        )
    else:
        priority = "MEDIUM_TERM"
        reasons.append(
            f"Risk score {risk_score} is below the SHORT_TERM threshold "
            f"({PRIORITY_THRESHOLDS['SHORT_TERM']})."
        )

    # Escalation: large exposed population overrides a lower risk-based tier.
    if (
        evidence.population_exposed >= LARGE_EXPOSED_POPULATION_ESCALATION_THRESHOLD
        and priority != "IMMEDIATE"
    ):
        reasons.append(
            f"Escalated to IMMEDIATE: {evidence.population_exposed:.0f} people "
            f"directly exposed, at or above the "
            f"{LARGE_EXPOSED_POPULATION_ESCALATION_THRESHOLD}-person escalation "
            "threshold regardless of the base risk band."
        )
        priority = "IMMEDIATE"

    if evidence.historical_events >= 3:
        reasons.append(
            f"{evidence.historical_events} prior disaster events recorded at this "
            "habitation - repeat exposure history."
        )

    if evidence.road_accessibility < 0.5:
        reasons.append(
            f"Road accessibility is low ({evidence.road_accessibility:.2f}), "
            "which will slow evacuation regardless of priority tier."
        )

    return PriorityResult(
        habitation_id=evidence.habitation_id,
        risk_score=risk_score,
        priority=priority,
        reasons=reasons,
        population_requiring_relocation=evidence.population_exposed,
    )