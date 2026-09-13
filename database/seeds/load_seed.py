from __future__ import annotations

from sqlalchemy import insert
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.models import (
    CapacityAssessment,
    Destination,
    Evidence,
    Habitation,
    Hazard,
    Recommendation,
    RelocationPriority,
    RiskAssessment,
    User,
)
from .seed_data import SEED_BATCHES

MODEL_MAP = {
    "users": User,
    "habitations": Habitation,
    "hazards": Hazard,
    "evidence": Evidence,
    "risk_assessments": RiskAssessment,
    "relocation_priorities": RelocationPriority,
    "destinations": Destination,
    "capacity_assessments": CapacityAssessment,
    "recommendations": Recommendation,
}


def load_seed_data(session: Session) -> dict[str, int]:
    counts: dict[str, int] = {}

    for batch in SEED_BATCHES:
        model = MODEL_MAP.get(batch.name)
        if model is None or not batch.rows:
            counts[batch.name] = 0
            continue
        session.execute(insert(model), batch.rows)
        counts[batch.name] = len(batch.rows)

    session.commit()
    return counts


if __name__ == "__main__":
    with SessionLocal() as session:
        print(load_seed_data(session))
