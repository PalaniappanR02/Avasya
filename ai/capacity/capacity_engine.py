"""
Turns a destination's nominal capacity into a defensible USABLE emergency
capacity - the guide calls this "the technical trap" for a reason: a
destination can look fine on paper (1,800 nominal) and still be unable to
safely receive that many people once real constraints are applied.

Pure function design, same as risk_engine.py and priority_engine.py:
calculate_capacity() takes typed inputs, returns a typed CapacityResult,
no hidden state, no file I/O inside this module.
"""

from __future__ import annotations

from ai.config.weights import (
    HEALTHCARE_DISTANCE_THRESHOLD_KM,
    HEALTHCARE_FAR_PENALTY_RATIO,
    SAFETY_RESERVE_RATIO,
    SANITATION_OK_BUFFER_RATIO,
    SANITATION_UNAVAILABLE_PENALTY_RATIO,
    WATER_AVAILABLE_BUFFER_RATIO,
    WATER_UNAVAILABLE_PENALTY_RATIO,
)
from ai.schemas.contracts import CapacityBreakdown, CapacityResult, Destination


def calculate_capacity(
    destination: Destination, population_requiring_relocation: float
) -> CapacityResult:
    """Compute the full nominal -> usable capacity waterfall for one
    destination, and check whether that usable capacity can actually
    absorb the population that needs to relocate there."""

    nominal = destination.nominal_capacity
    available_space = nominal - destination.existing_occupancy

    water_ratio = (
        WATER_AVAILABLE_BUFFER_RATIO
        if destination.water_available
        else WATER_UNAVAILABLE_PENALTY_RATIO
    )
    water_constraint = round(nominal * water_ratio)

    sanitation_ratio = (
        SANITATION_OK_BUFFER_RATIO
        if destination.sanitation_ok
        else SANITATION_UNAVAILABLE_PENALTY_RATIO
    )
    sanitation_constraint = round(nominal * sanitation_ratio)

    healthcare_constraint = (
        round(nominal * HEALTHCARE_FAR_PENALTY_RATIO)
        if destination.healthcare_distance_km > HEALTHCARE_DISTANCE_THRESHOLD_KM
        else 0
    )

    safety_reserve = round(nominal * SAFETY_RESERVE_RATIO)

    usable_capacity = (
        available_space
        - water_constraint
        - sanitation_constraint
        - healthcare_constraint
        - safety_reserve
    )
    # Usable capacity can't meaningfully go negative - floor at 0 rather than
    # reporting a nonsensical negative number of "usable seats".
    usable_capacity = max(0, usable_capacity)

    breakdown = CapacityBreakdown(
        nominal_capacity=nominal,
        existing_occupancy=destination.existing_occupancy,
        available_space=available_space,
        water_constraint=water_constraint,
        sanitation_constraint=sanitation_constraint,
        healthcare_constraint=healthcare_constraint,
        safety_reserve=safety_reserve,
        usable_capacity=usable_capacity,
    )

    capacity_sufficient = usable_capacity >= population_requiring_relocation

    reasons: list[str] = []
    if not destination.water_available:
        reasons.append("No confirmed water supply - larger capacity penalty applied.")
    if not destination.sanitation_ok:
        reasons.append("Sanitation not confirmed adequate - larger capacity penalty applied.")
    if destination.healthcare_distance_km > HEALTHCARE_DISTANCE_THRESHOLD_KM:
        reasons.append(
            f"Nearest healthcare is {destination.healthcare_distance_km:.1f} km away, "
            f"beyond the {HEALTHCARE_DISTANCE_THRESHOLD_KM:.0f} km threshold."
        )
    if destination.existing_occupancy / nominal > 0.5 if nominal else False:
        reasons.append(
            f"Already at {destination.existing_occupancy}/{nominal} "
            f"({destination.existing_occupancy / nominal:.0%}) existing occupancy."
        )

    if capacity_sufficient:
        reasons.append(
            f"Usable capacity {usable_capacity} meets the "
            f"{population_requiring_relocation:.0f} people requiring relocation."
        )
    else:
        reasons.append(
            f"Usable capacity {usable_capacity} is short of the "
            f"{population_requiring_relocation:.0f} people requiring relocation "
            f"by {population_requiring_relocation - usable_capacity:.0f}."
        )

    explanation = (
        f"{destination.name} ({destination.destination_id}): nominal {nominal} "
        f"- {destination.existing_occupancy} occupied - {water_constraint} water "
        f"- {sanitation_constraint} sanitation - {healthcare_constraint} healthcare "
        f"- {safety_reserve} safety reserve = {usable_capacity} usable. "
        f"{'SUFFICIENT' if capacity_sufficient else 'INSUFFICIENT'} for "
        f"{population_requiring_relocation:.0f} people."
    )

    return CapacityResult(
        destination_id=destination.destination_id,
        population_requiring_relocation=population_requiring_relocation,
        capacity_breakdown=breakdown,
        capacity_sufficient=capacity_sufficient,
        reasons=reasons,
        explanation=explanation,
    )