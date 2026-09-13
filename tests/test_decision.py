from backend.services.decision import risk_level, score_risk


def test_locked_risk_fixture_scores_87_and_contributions_sum() -> None:
    score, contributions = score_risk({
        "hazard_exposure": 100,
        "population": 80,
        "vulnerability": 90,
        "historical_events": 100,
        "road_accessibility": 46.153846,
    })

    assert score == 87.0
    assert round(sum(contributions.values()), 2) == score
    assert risk_level(score) == "HIGH"


def test_risk_score_is_bounded_and_levels_are_locked() -> None:
    score, _ = score_risk({
        "hazard_exposure": 200,
        "population": -10,
        "vulnerability": 200,
        "historical_events": 200,
        "road_accessibility": 200,
    })

    assert score == 80.0
    assert risk_level(0) == "LOW"
    assert risk_level(49.99) == "LOW"
    assert risk_level(50) == "MEDIUM"
    assert risk_level(74.99) == "MEDIUM"
    assert risk_level(75) == "HIGH"
