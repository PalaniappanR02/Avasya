from __future__ import annotations

from ai.priority.priority_engine import calculate_priority
from ai.risk.risk_engine import calculate_risk
from ai.risk.test_risk_engine import make_evidence


def test_high_risk_gives_immediate_priority():
    evidence = make_evidence(
        hazard_exposure=1.0,
        vulnerability=0.9,
        historical_events=8,
        road_accessibility=0.1,
        population=5000,
        population_exposed=100.0,
    )
    risk_result = calculate_risk(evidence)
    assert risk_result.risk_score >= 70
    priority_result = calculate_priority(evidence, risk_result)
    assert priority_result.priority == "IMMEDIATE"
    assert len(priority_result.reasons) >= 1


def test_low_risk_gives_medium_term_priority():
    evidence = make_evidence(
        hazard_exposure=0.05,
        vulnerability=0.1,
        historical_events=0,
        road_accessibility=1.0,
        population_exposed=10.0,
    )
    risk_result = calculate_risk(evidence)
    priority_result = calculate_priority(evidence, risk_result)
    assert priority_result.priority == "MEDIUM_TERM"


def test_large_exposed_population_escalates_to_immediate():
    evidence = make_evidence(
        hazard_exposure=0.3,
        vulnerability=0.3,
        historical_events=1,
        road_accessibility=0.8,
        population=2000,
        population_exposed=600.0,
    )
    risk_result = calculate_risk(evidence)
    priority_result = calculate_priority(evidence, risk_result)
    assert priority_result.priority == "IMMEDIATE"
    assert any("Escalated" in reason for reason in priority_result.reasons)


def test_reasons_are_never_empty():
    evidence = make_evidence()
    risk_result = calculate_risk(evidence)
    priority_result = calculate_priority(evidence, risk_result)
    assert len(priority_result.reasons) > 0


def test_population_requiring_relocation_matches_exposed():
    evidence = make_evidence(population_exposed=345.0)
    risk_result = calculate_risk(evidence)
    priority_result = calculate_priority(evidence, risk_result)
    assert priority_result.population_requiring_relocation == 345.0