from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import (
    CapacityAssessment,
    Destination,
    Evidence,
    Habitation,
    Recommendation,
    RelocationPriority,
    RiskAssessment,
    User,
)
from backend.models.enums import DataOrigin


WEIGHTS = {
    "hazard_exposure": 0.35,
    "population": 0.20,
    "vulnerability": 0.20,
    "historical_events": 0.12,
    "road_accessibility": 0.13,
}


def risk_level(score: float) -> str:
    bounded = max(0.0, min(100.0, score))
    if bounded < 50:
        return "LOW"
    if bounded < 75:
        return "MEDIUM"
    return "HIGH"


def score_risk(components: dict[str, float]) -> tuple[float, dict[str, float]]:
    contributions = {
        name: round(max(0.0, min(100.0, components.get(name, 0.0))) * weight, 2)
        for name, weight in WEIGHTS.items()
    }
    return round(max(0.0, min(100.0, sum(contributions.values()))), 2), contributions


@dataclass
class DecisionResult:
    risk: RiskAssessment
    priority: RelocationPriority
    recommendation: Recommendation


class DecisionService:
    """Persists decision outputs without changing the locked scoring method."""

    def __init__(self, session: Session):
        self.session = session

    def assess(self, habitation_id: int) -> DecisionResult:
        habitation = self.session.get(Habitation, habitation_id)
        if habitation is None:
            raise ValueError("Habitation not found")

        components, warnings, evidence_quality, evidence_ids = self._components(habitation)
        score, contributions = score_risk(components)
        now = datetime.now(timezone.utc)
        risk = RiskAssessment(
            habitation_id=habitation.id,
            overall_risk_score=score,
            risk_level=risk_level(score),
            confidence_score=0 if warnings else 100,
            model_version="locked-weighted-v1",
            input_snapshot={"components": components, "evidence_ids": evidence_ids},
            normalized_values=components,
            weights=WEIGHTS,
            contributions=contributions,
            reasons={"method": "Persisted evidence only", "limitations": warnings},
            warnings={"items": warnings},
            freshness={"assessed_at": now.isoformat()},
            data_quality=evidence_quality,
            calculation_details={
                "formula": "0.35*hazard_exposure + 0.20*population + "
                "0.20*vulnerability + 0.12*historical_events + "
                "0.13*road_accessibility",
                "contribution_sum": round(sum(contributions.values()), 2),
            },
            data_origin=DataOrigin.MIXED if warnings else DataOrigin.REAL,
            generated_at=now,
        )
        self.session.add(risk)
        self.session.flush()

        priority_label = "IMMEDIATE" if risk.risk_level == "HIGH" else (
            "HIGH" if risk.risk_level == "MEDIUM" else "MONITOR"
        )
        required_capacity = max(1, habitation.population or habitation.households or 1)
        priority = RelocationPriority(
            habitation_id=habitation.id,
            priority_score=score,
            priority_label=priority_label,
            rationale={
                "risk_assessment_id": risk.id,
                "reason": f"Risk level {risk.risk_level}; relocation requirement is {required_capacity}.",
                "required_capacity": required_capacity,
                "warnings": warnings,
            },
            data_origin=risk.data_origin,
        )
        self.session.add(priority)
        self.session.flush()

        destination, capacity = self._select_destination(habitation.id, required_capacity)
        if destination is None:
            summary = "NO_ELIGIBLE_DESTINATION"
            details: dict[str, Any] = {
                "reason": "No destination passed usable_capacity >= required_capacity.",
                "required_capacity": required_capacity,
            }
            destination_id = None
        else:
            summary = f"Relocate to {destination.name}"
            details = {
                "reason": "Highest-priority eligible destination selected.",
                "capacity": {
                    "usable_capacity": capacity.usable_capacity,
                    "required_capacity": capacity.required_capacity,
                    "capacity_gap": capacity.capacity_gap,
                },
                "eligibility": True,
            }
            destination_id = destination.id
            priority.destination_id = destination.id

        recommendation = Recommendation(
            risk_assessment_id=risk.id,
            destination_id=destination_id,
            relocation_priority_id=priority.id,
            recommendation_type="IMMEDIATE_RELOCATION" if priority_label == "IMMEDIATE" else "RELOCATION_REVIEW",
            summary=summary,
            details=details,
            confidence_score=risk.confidence_score,
            data_origin=risk.data_origin,
        )
        self.session.add(recommendation)
        self.session.commit()
        self.session.refresh(recommendation)
        return DecisionResult(risk=risk, priority=priority, recommendation=recommendation)

    def _components(
        self, habitation: Habitation
    ) -> tuple[dict[str, float], list[str], dict[str, Any], dict[str, list[int]]]:
        warnings: list[str] = []
        quality: dict[str, Any] = {"origin": habitation.data_origin.value}
        linked = list(self.session.scalars(
            select(Evidence).where(Evidence.habitation_id == habitation.id)
        ).all())
        linked_hazard = [
            item for item in linked
            if item.hazard_id is not None or item.evidence_type in {"flood", "hazard"}
        ]
        linked_history = [
            item for item in linked
            if item.evidence_type in {"flood", "historical_events", "cyclone_imd"}
        ]
        linked_roads = [
            item for item in linked
            if item.evidence_type in {"roads", "highways", "road_accessibility"}
        ]
        hazard_value = 100.0 if linked_hazard else 0.0
        historical_value = 100.0 if linked_history else 0.0
        if not linked_hazard:
            warnings.append("No directly habitation-linked hazard evidence was found.")
        if not linked_history:
            warnings.append("No directly habitation-linked historical event evidence was found.")

        maximum = self.session.scalar(select(func.max(Habitation.population))) or 0
        population_value = (
            round(min(100.0, (habitation.population or 0) / maximum * 100), 2)
            if maximum else 0.0
        )

        vulnerability_value = 0.0
        warnings.append("Vulnerability data is district-level and not linked to this habitation.")

        road_value = 0.0
        if not linked_roads:
            warnings.append("Road accessibility distance evidence is unavailable; component recorded as missing.")
        if not habitation.population and not habitation.households:
            warnings.append("Population and household inputs are unavailable for this habitation.")
        quality["missing_components"] = [
            name for name, value in {
                "hazard_exposure": hazard_value,
                "vulnerability": vulnerability_value,
                "historical_events": historical_value,
                "road_accessibility": road_value,
            }.items() if value == 0
        ]
        return {
            "hazard_exposure": hazard_value,
            "population": population_value,
            "vulnerability": vulnerability_value,
            "historical_events": historical_value,
            "road_accessibility": road_value,
        }, warnings, quality, {
            "hazard_exposure": [item.id for item in linked_hazard],
            "historical_events": [item.id for item in linked_history],
            "road_accessibility": [item.id for item in linked_roads],
        }

    def _select_destination(
        self, habitation_id: int, required_capacity: int
    ) -> tuple[Destination | None, CapacityAssessment | None]:
        rows = self.session.execute(
            select(Destination, CapacityAssessment)
            .join(CapacityAssessment, CapacityAssessment.destination_id == Destination.id)
            .where(CapacityAssessment.habitation_id == habitation_id)
            .order_by(Destination.risk_score.asc().nulls_last(), Destination.id.asc())
        ).all()
        for destination, capacity in rows:
            if capacity.usable_capacity >= required_capacity:
                return destination, capacity
        return None, None
