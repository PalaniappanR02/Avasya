from __future__ import annotations

import os

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from backend.core.database import SessionLocal
from backend.models import (
    CapacityAssessment,
    Destination,
    Habitation,
    Recommendation,
    RiskAssessment,
    User,
)
from backend.models.enums import DataOrigin
from backend.services.decision import DecisionService


def main() -> None:
    db = SessionLocal()
    try:
        habitation = db.scalar(select(Habitation).order_by(Habitation.id))
        if habitation is None:
            raise RuntimeError("No real habitation exists; run Census ingestion first.")

        officer = db.scalar(select(User).where(User.email == "demo.officer@avasya.local"))
        if officer is None:
            officer = User(
                email="demo.officer@avasya.local",
                full_name="AVASYA Demo Officer",
                role="officer",
                data_origin=DataOrigin.SYNTHETIC_DEMO,
            )
            db.add(officer)
            db.flush()

        destinations = {}
        for name, risk, nominal in (
            ("D02 Synthetic Insufficient Shelter", 20, 1),
            ("D04 Synthetic Eligible Shelter", 30, max(1, habitation.population or habitation.households or 1) + 100),
        ):
            destination = db.scalar(select(Destination).where(Destination.name == name))
            if destination is None:
                destination = Destination(
                    name=name,
                    destination_type="DEMO_SHELTER",
                    district=habitation.district,
                    state=habitation.state,
                    country="India",
                    geom=WKTElement("SRID=4326;POINT(78 12)", srid=4326),
                    capacity_total=nominal,
                    capacity_available=nominal,
                    risk_score=risk,
                    data_origin=DataOrigin.SYNTHETIC_DEMO,
                )
                db.add(destination)
                db.flush()
            destinations[name] = destination

        required = max(1, habitation.population or habitation.households or 1)
        for destination, occupancy in (
            (destinations["D02 Synthetic Insufficient Shelter"], destination.capacity_total),
            (destinations["D04 Synthetic Eligible Shelter"], 0),
        ):
            existing = db.scalar(
                select(CapacityAssessment).where(
                    CapacityAssessment.destination_id == destination.id,
                    CapacityAssessment.habitation_id == habitation.id,
                )
            )
            if existing is None:
                nominal = destination.capacity_total or 0
                calculated_usable = nominal - occupancy - 0 - 0 - 0
                # The schema requires usable_capacity to be non-negative; retain
                # the signed shortfall in capacity_gap and the raw calculation.
                usable = max(0, calculated_usable)
                db.add(CapacityAssessment(
                    destination_id=destination.id,
                    habitation_id=habitation.id,
                    nominal_capacity=nominal,
                    existing_occupancy=occupancy,
                    water_constraint=0,
                    sanitation_constraint=0,
                    safety_reserve=0,
                    required_capacity=required,
                    usable_capacity=usable,
                    capacity_gap=usable - required,
                    status="ELIGIBLE" if usable >= required else "INSUFFICIENT",
                    assessment_details={
                        "synthetic_demo": True,
                        "calculated_usable_capacity": calculated_usable,
                    },
                    data_origin=DataOrigin.SYNTHETIC_DEMO,
                ))
        db.commit()
        existing = db.scalar(
            select(Recommendation)
            .join(RiskAssessment, Recommendation.risk_assessment_id == RiskAssessment.id)
            .where(RiskAssessment.habitation_id == habitation.id)
            .order_by(Recommendation.created_at.desc())
        )
        if existing is not None:
            print({
                "habitation_id": habitation.id,
                "recommendation_id": existing.id,
                "destination_id": existing.destination_id,
                "idempotent": True,
                "officer_email": officer.email,
            })
            return
        result = DecisionService(db).assess(habitation.id)
        print({
            "habitation_id": habitation.id,
            "risk_id": result.risk.id,
            "risk_score": result.risk.overall_risk_score,
            "priority_id": result.priority.id,
            "recommendation_id": result.recommendation.id,
            "destination_id": result.recommendation.destination_id,
            "officer_email": officer.email,
        })
    finally:
        db.close()


if __name__ == "__main__":
    main()
