"""
Scores ONE candidate destination for ONE habitation across the suitability
criteria we actually have real data for. Mirrors risk_engine.py's pattern
deliberately: single-entity, pure function, fully explainable.

Ranking MULTIPLE destinations against each other and picking the winner is
recommendation_engine.py's job, not this file's - destination_scorer.py
only answers "how good is THIS ONE destination for THIS ONE habitation",
so it stays independently testable exactly like the guide asks for.
"""

from __future__ import annotations

import math

from ai.config.weights import (
    DESTINATION_DISTANCE_MAX_KM,
    HEALTHCARE_ACCESS_MAX_KM,
    SUITABILITY_WEIGHTS,
)
from ai.schemas.contracts import (
    CapacityResult,
    Destination,
    HabitationEvidence,
    SuitabilityBreakdown,
    SuitabilityResult,
)

EARTH_RADIUS_KM = 6371.0


def _haversine_distance_km(
    lon1: float, lat1: float, lon2: float, lat2: float
) -> float:
    """Real great-circle distance between two lon/lat points - calculated
    from the actual geometry both habitations and destinations already
    carry, not looked up or invented. This is standard spherical-earth
    approximation, accurate enough for single-district relocation planning."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def _linear_decay_score(distance_km: float, max_km: float) -> float:
    """100 at distance=0, decaying linearly to 0 at distance=max_km, floored
    at 0 beyond that - never negative, never extrapolated past the range."""
    if max_km <= 0:
        raise ValueError("max_km must be positive")
    score = 100 * (1 - distance_km / max_km)
    return max(0.0, min(100.0, score))


def score_destination(
    habitation: HabitationEvidence,
    destination: Destination,
    capacity_result: CapacityResult,
) -> SuitabilityResult:
    """Compute the weighted suitability score for one destination, given the
    capacity check that was already run for it. capacity_result must be for
    THIS destination and THIS habitation's population - the caller is
    responsible for passing a matching pair (recommendation_engine.py does
    this when it loops over multiple destinations)."""

    distance_km = _haversine_distance_km(
        habitation.geometry.coordinates[0],
        habitation.geometry.coordinates[1],
        destination.geometry.coordinates[0],
        destination.geometry.coordinates[1],
    )

    # Capacity adequacy: how comfortably usable capacity covers the
    # population needing relocation, capped at 100 (more headroom past
    # "enough" doesn't make a destination progressively more suitable).
    population = capacity_result.population_requiring_relocation
    usable = capacity_result.capacity_breakdown.usable_capacity
    if population <= 0:
        capacity_adequacy_score = 100.0
    else:
        capacity_adequacy_score = max(0.0, min(100.0, (usable / population) * 100))

    water_score = 100.0 if destination.water_available else 0.0
    sanitation_score = 100.0 if destination.sanitation_ok else 0.0
    healthcare_score = _linear_decay_score(
        destination.healthcare_distance_km, HEALTHCARE_ACCESS_MAX_KM
    )
    road_score = destination.road_access * 100
    distance_score = _linear_decay_score(distance_km, DESTINATION_DISTANCE_MAX_KM)

    capacity_contribution = capacity_adequacy_score * SUITABILITY_WEIGHTS["capacity_adequacy"]
    water_contribution = water_score * SUITABILITY_WEIGHTS["water"]
    sanitation_contribution = sanitation_score * SUITABILITY_WEIGHTS["sanitation"]
    healthcare_contribution = healthcare_score * SUITABILITY_WEIGHTS["healthcare_access"]
    road_contribution = road_score * SUITABILITY_WEIGHTS["road_access"]
    distance_contribution = distance_score * SUITABILITY_WEIGHTS["distance"]

    suitability_score = round(
        capacity_contribution
        + water_contribution
        + sanitation_contribution
        + healthcare_contribution
        + road_contribution
        + distance_contribution,
        1,
    )

    breakdown = SuitabilityBreakdown(
        capacity_adequacy_contribution=round(capacity_contribution, 1),
        water_contribution=round(water_contribution, 1),
        sanitation_contribution=round(sanitation_contribution, 1),
        healthcare_access_contribution=round(healthcare_contribution, 1),
        road_access_contribution=round(road_contribution, 1),
        distance_contribution=round(distance_contribution, 1),
    )

    reasons: list[str] = []
    if not capacity_result.capacity_sufficient:
        reasons.append("Insufficient usable capacity for this habitation's exposed population.")
    if not destination.water_available:
        reasons.append("No confirmed water supply.")
    if not destination.sanitation_ok:
        reasons.append("Sanitation not confirmed adequate.")
    if destination.healthcare_distance_km > HEALTHCARE_ACCESS_MAX_KM / 2:
        reasons.append(f"Healthcare access is limited ({destination.healthcare_distance_km:.1f} km away).")
    if destination.road_access < 0.5:
        reasons.append(f"Road access is poor ({destination.road_access:.2f}).")
    if distance_km > DESTINATION_DISTANCE_MAX_KM / 2:
        reasons.append(f"Relatively far from the habitation ({distance_km:.1f} km).")
    if not reasons:
        reasons.append("Meets capacity, water, sanitation, healthcare and road access criteria.")

    explanation = (
        f"{destination.name} scored {suitability_score}/100 for {habitation.name}: "
        f"capacity adequacy {capacity_adequacy_score:.0f}, water {water_score:.0f}, "
        f"sanitation {sanitation_score:.0f}, healthcare access {healthcare_score:.0f}, "
        f"road access {road_score:.0f}, distance {distance_score:.0f} "
        f"({distance_km:.1f} km away)."
    )

    return SuitabilityResult(
        destination_id=destination.destination_id,
        habitation_id=habitation.habitation_id,
        suitability_score=suitability_score,
        distance_km=round(distance_km, 2),
        capacity_sufficient=capacity_result.capacity_sufficient,
        suitability_breakdown=breakdown,
        reasons=reasons,
        explanation=explanation,
    )