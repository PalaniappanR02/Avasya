from __future__ import annotations

import pytest

from ai.risk.risk_engine import calculate_risk
from ai.schemas.contracts import Geometry, HabitationEvidence


def make_evidence(**overrides) -> HabitationEvidence:
    """Builds a valid HabitationEvidence with sane defaults, so each test
    only has to override the one or two fields it actually cares about."""
    base = dict(
        habitation_id="H_TEST",
        name="Test Village",
        population=1000,
        population_exposed=500.0,
        hazard_exposure=0.5,
        vulnerability=0.5,
        historical_events=2,
        hospital_distance_km=1.0,
        nearest_road_distance_km=0.5,
        road_accessibility=0.5,
        nearest_relief_center_id="RC01",
        nearest_relief_center_distance_km=1.0,
        nearest_relief_center_capacity=1000,
        nearest_relief_center_water_available=True,
        geometry=Geometry(type="Point", coordinates=(80.0, 13.0)),
        district="Thanjavur",
        data_source="SYNTHETIC_DEMO",
        data_quality="SYNTHETIC_DEMO",
    )
    base.update(overrides)
    return HabitationEvidence(**base)


def test_zero_hazard_zero_vulnerability_gives_low_score():
    evidence = make_evidence(
        hazard_exposure=0.0,
        vulnerability=0.0,
        historical_events=0,
        road_accessibility=1.0,
        population=0,
        population_exposed=0.0,
    )
    result = calculate_risk(evidence)
    assert result.risk_score == 0.0
    assert result.risk_level == "LOW"


def test_maximum_risk_inputs_give_max_score():
    evidence = make_evidence(
        hazard_exposure=1.0,
        vulnerability=1.0,
        historical_events=10,
        road_accessibility=0.0,
        population=10_000,
        population_exposed=10_000.0,
    )
    result = calculate_risk(evidence)
    assert result.risk_score == 100.0
    assert result.risk_level == "CRITICAL"


def test_population_above_cap_does_not_exceed_100_contribution():
    evidence = make_evidence(population=50_000, population_exposed=0.0)
    result = calculate_risk(evidence)
    assert result.risk_breakdown.population_contribution <= 20.0 + 0.05


def test_breakdown_sums_to_risk_score():
    evidence = make_evidence()
    result = calculate_risk(evidence)
    total = (
        result.risk_breakdown.hazard_exposure_contribution
        + result.risk_breakdown.population_contribution
        + result.risk_breakdown.vulnerability_contribution
        + result.risk_breakdown.historical_contribution
        + result.risk_breakdown.road_contribution
    )
    assert abs(total - result.risk_score) < 0.2


def test_poor_road_access_increases_risk_vs_good_access():
    good_roads = make_evidence(road_accessibility=1.0)
    bad_roads = make_evidence(road_accessibility=0.0)
    result_good = calculate_risk(good_roads)
    result_bad = calculate_risk(bad_roads)
    assert result_bad.risk_score > result_good.risk_score


def test_invalid_hazard_exposure_out_of_range_raises():
    with pytest.raises(Exception):
        make_evidence(hazard_exposure=1.5)


def test_population_exposed_cannot_exceed_population():
    with pytest.raises(Exception):
        make_evidence(population=100, population_exposed=500.0)


def test_real_sample_habitation_h001():
    evidence = make_evidence(
        habitation_id="H001",
        name="Krishnapuram Village",
        population=1240,
        population_exposed=620.01,
        hazard_exposure=0.5,
        vulnerability=0.71,
        historical_events=3,
        road_accessibility=1.0,
    )
    result = calculate_risk(evidence)
    assert 0 <= result.risk_score <= 100
    assert result.habitation_id == "H001"