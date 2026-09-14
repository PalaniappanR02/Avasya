from __future__ import annotations

from ai.capacity.test_capacity_engine import make_destination
from ai.recommendation.recommendation_engine import (
    generate_recommendation,
    what_if_unavailable,
)
from ai.risk.test_risk_engine import make_evidence


def make_five_destinations():
    """A small realistic set with a clear winner, a clear runner-up, and a
    clearly insufficient option - similar in spirit to the real repo data."""
    d1 = make_destination(
        destination_id="D01", nominal_capacity=1800, existing_occupancy=300,
        water_available=True, sanitation_ok=True, healthcare_distance_km=2.0, road_access=0.9,
    )
    d2 = make_destination(
        destination_id="D02", nominal_capacity=1200, existing_occupancy=300,
        water_available=True, sanitation_ok=True, healthcare_distance_km=4.0, road_access=0.7,
    )
    d3 = make_destination(
        destination_id="D03", nominal_capacity=300, existing_occupancy=250,
        water_available=False, sanitation_ok=False, healthcare_distance_km=9.0, road_access=0.3,
    )
    return [d1, d2, d3]


def test_recommends_a_sufficient_destination_not_the_highest_raw_score_insufficient_one():
    habitation = make_evidence(habitation_id="H_REC")
    destinations = make_five_destinations()
    result = generate_recommendation(habitation, destinations, population_requiring_relocation=600)
    assert result.recommended_destination_id is not None
    recommended = next(
        r for r in result.destinations_ranked if r.destination_id == result.recommended_destination_id
    )
    assert recommended.capacity_sufficient is True


def test_insufficient_destination_never_recommended_even_if_only_option():
    habitation = make_evidence(habitation_id="H_NOOPT")
    destinations = [
        make_destination(destination_id="D_SMALL", nominal_capacity=50, existing_occupancy=40)
    ]
    result = generate_recommendation(habitation, destinations, population_requiring_relocation=1000)
    assert result.recommended_destination_id is None
    assert "No candidate destination has sufficient" in result.explanation


def test_recommended_reasons_and_rejected_reasons_are_populated():
    habitation = make_evidence(habitation_id="H_REASONS")
    destinations = make_five_destinations()
    result = generate_recommendation(habitation, destinations, population_requiring_relocation=600)
    assert len(result.recommended_reasons) > 0
    if result.next_best_destination_id:
        assert len(result.next_best_rejected_reasons) > 0


def test_what_if_unavailable_excludes_and_recalculates():
    """The guide's specific demo moment: recommend D01, then mark D01
    unavailable and confirm the system picks a different destination."""
    habitation = make_evidence(habitation_id="H_WHATIF")
    destinations = make_five_destinations()

    first = generate_recommendation(habitation, destinations, population_requiring_relocation=600)
    assert first.recommended_destination_id == "D01"

    second = what_if_unavailable(
        habitation, destinations, population_requiring_relocation=600,
        unavailable_destination_id="D01",
    )
    assert second.recommended_destination_id != "D01"
    assert "D01" in second.excluded_destination_ids
    # D01 should not even appear in the ranked list anymore
    assert all(r.destination_id != "D01" for r in second.destinations_ranked)


def test_what_if_can_be_chained_for_multiple_unavailable_destinations():
    habitation = make_evidence(habitation_id="H_CHAIN")
    destinations = make_five_destinations()

    first = generate_recommendation(habitation, destinations, population_requiring_relocation=600)
    second = what_if_unavailable(
        habitation, destinations, population_requiring_relocation=600,
        unavailable_destination_id=first.recommended_destination_id,
    )
    third = what_if_unavailable(
        habitation, destinations, population_requiring_relocation=600,
        unavailable_destination_id=second.recommended_destination_id,
        already_excluded=second.excluded_destination_ids,
    )
    assert len(third.excluded_destination_ids) == 2
    assert third.recommended_destination_id not in third.excluded_destination_ids


def test_generated_at_timestamp_is_present_for_audit_trail():
    habitation = make_evidence(habitation_id="H_AUDIT")
    destinations = make_five_destinations()
    result = generate_recommendation(habitation, destinations, population_requiring_relocation=600)
    assert result.generated_at  # non-empty ISO timestamp string
    assert "T" in result.generated_at