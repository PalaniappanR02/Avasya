from __future__ import annotations

import pytest

from ai.capacity.capacity_engine import calculate_capacity
from ai.schemas.contracts import Destination, Geometry


def make_destination(**overrides) -> Destination:
    base = dict(
        destination_id="RC_TEST",
        name="Test Relief Center",
        nominal_capacity=1800,
        existing_occupancy=300,
        water_available=True,
        sanitation_ok=True,
        healthcare_distance_km=2.1,
        road_access=0.9,
        geometry=Geometry(type="Point", coordinates=(80.2, 13.4)),
        district="Thanjavur",
        data_source="SYNTHETIC_DEMO",
        data_quality="SYNTHETIC_DEMO",
    )
    base.update(overrides)
    return Destination(**base)


def test_guide_worked_example_lands_close_with_documented_ratios():
    """The guide's own illustrative example (nominal 1800, occupancy 300,
    flat -80/-70/-100 deductions) reaches usable=1250, just above the 1240
    required. Our engine uses documented RATIOS instead of the guide's flat
    illustrative numbers (see config/weights.py for why), so it will not
    reproduce 1250 exactly - and that's expected, not a bug. With our ratios
    this specific case lands at usable=1212, just short of 1240: a genuine,
    honest near-miss rather than a forced match to the guide's example."""
    destination = make_destination(
        nominal_capacity=1800, existing_occupancy=300, healthcare_distance_km=2.1
    )
    result = calculate_capacity(destination, population_requiring_relocation=1240)
    assert result.capacity_breakdown.usable_capacity == 1212
    assert result.capacity_sufficient is False
    assert "short" in result.reasons[-1]


def test_insufficient_capacity_is_flagged_not_hidden():
    destination = make_destination(nominal_capacity=900, existing_occupancy=150)
    result = calculate_capacity(destination, population_requiring_relocation=1240)
    assert result.capacity_sufficient is False
    assert any("short" in r or "Insufficient" in r for r in result.reasons + [result.explanation])


def test_no_water_or_sanitation_reduces_usable_capacity():
    good = make_destination(water_available=True, sanitation_ok=True)
    bad = make_destination(water_available=False, sanitation_ok=False)
    result_good = calculate_capacity(good, population_requiring_relocation=100)
    result_bad = calculate_capacity(bad, population_requiring_relocation=100)
    assert (
        result_bad.capacity_breakdown.usable_capacity
        < result_good.capacity_breakdown.usable_capacity
    )
    assert len(result_bad.reasons) > len(result_good.reasons)


def test_usable_capacity_never_negative():
    destination = make_destination(nominal_capacity=100, existing_occupancy=100)
    result = calculate_capacity(destination, population_requiring_relocation=50)
    assert result.capacity_breakdown.usable_capacity == 0
    assert result.capacity_sufficient is False


def test_far_healthcare_applies_penalty():
    near = make_destination(healthcare_distance_km=2.0)
    far = make_destination(healthcare_distance_km=8.0)
    result_near = calculate_capacity(near, population_requiring_relocation=100)
    result_far = calculate_capacity(far, population_requiring_relocation=100)
    assert result_far.capacity_breakdown.healthcare_constraint > 0
    assert result_near.capacity_breakdown.healthcare_constraint == 0
    assert (
        result_far.capacity_breakdown.usable_capacity
        < result_near.capacity_breakdown.usable_capacity
    )


def test_existing_occupancy_cannot_exceed_nominal_capacity():
    with pytest.raises(Exception):
        make_destination(nominal_capacity=500, existing_occupancy=600)


def test_real_destination_rc03_from_repo():
    """Sanity check against the actual RC03 record in data/destinations.json -
    the one deliberately lacking water and sanitation."""
    destination = make_destination(
        destination_id="RC03",
        name="Relief Center East",
        nominal_capacity=900,
        existing_occupancy=150,
        water_available=False,
        sanitation_ok=False,
        healthcare_distance_km=5.6,
        road_access=0.6,
    )
    result = calculate_capacity(destination, population_requiring_relocation=620.01)
    assert result.destination_id == "RC03"
    assert result.capacity_breakdown.water_constraint > 0
    assert result.capacity_breakdown.sanitation_constraint > 0
    assert result.capacity_breakdown.healthcare_constraint > 0  # 5.6 > 5.0 threshold