from __future__ import annotations

from ai.capacity.capacity_engine import calculate_capacity
from ai.capacity.test_capacity_engine import make_destination
from ai.risk.test_risk_engine import make_evidence
from ai.suitability.destination_scorer import _haversine_distance_km, score_destination


def test_haversine_zero_distance_for_same_point():
    d = _haversine_distance_km(80.2, 13.4, 80.2, 13.4)
    assert d == 0.0


def test_haversine_known_short_distance_is_reasonable():
    # ~0.01 degree apart at this latitude is roughly ~1.1 km
    d = _haversine_distance_km(80.20, 13.40, 80.21, 13.40)
    assert 0.5 < d < 2.0


def test_fully_serviced_nearby_destination_scores_high():
    habitation = make_evidence(habitation_id="H_A")
    destination = make_destination(
        water_available=True,
        sanitation_ok=True,
        healthcare_distance_km=1.0,
        road_access=1.0,
    )
    # place destination essentially on top of the habitation for a near-zero distance
    destination = destination.model_copy(
        update={"geometry": habitation.geometry}
    )
    capacity_result = calculate_capacity(destination, population_requiring_relocation=100)
    result = score_destination(habitation, destination, capacity_result)
    assert result.suitability_score > 80


def test_poor_destination_scores_low():
    habitation = make_evidence(habitation_id="H_B")
    destination = make_destination(
        water_available=False,
        sanitation_ok=False,
        healthcare_distance_km=20.0,
        road_access=0.1,
        nominal_capacity=200,
        existing_occupancy=190,
    )
    capacity_result = calculate_capacity(destination, population_requiring_relocation=500)
    result = score_destination(habitation, destination, capacity_result)
    assert result.suitability_score < 40
    assert result.capacity_sufficient is False
    assert len(result.reasons) > 1


def test_insufficient_capacity_is_reflected_in_reasons():
    habitation = make_evidence(habitation_id="H_C")
    destination = make_destination(nominal_capacity=100, existing_occupancy=90)
    capacity_result = calculate_capacity(destination, population_requiring_relocation=1000)
    result = score_destination(habitation, destination, capacity_result)
    assert result.capacity_sufficient is False
    assert any("capacity" in r.lower() for r in result.reasons)


def test_two_real_destinations_rank_differently_for_h001():
    """Sanity check with realistic values matching the repo's real H001 and
    RC01/RC03 records - RC01 should clearly outscore RC03."""
    h001 = make_evidence(
        habitation_id="H001",
        name="Krishnapuram Village",
    )
    h001 = h001.model_copy(update={"geometry": h001.geometry})

    rc01 = make_destination(
        destination_id="RC01",
        name="Relief Center North",
        nominal_capacity=1800,
        existing_occupancy=300,
        water_available=True,
        sanitation_ok=True,
        healthcare_distance_km=2.2,
        road_access=0.9,
    )
    rc03 = make_destination(
        destination_id="RC03",
        name="Relief Center East",
        nominal_capacity=900,
        existing_occupancy=150,
        water_available=False,
        sanitation_ok=False,
        healthcare_distance_km=5.6,
        road_access=0.6,
    )

    cap_rc01 = calculate_capacity(rc01, population_requiring_relocation=620.01)
    cap_rc03 = calculate_capacity(rc03, population_requiring_relocation=620.01)

    result_rc01 = score_destination(h001, rc01, cap_rc01)
    result_rc03 = score_destination(h001, rc03, cap_rc03)

    assert result_rc01.suitability_score > result_rc03.suitability_score