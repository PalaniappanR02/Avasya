from __future__ import annotations

from backend.models import Base
from backend.models.capacity_assessment import CapacityAssessment
from backend.models.destination import Destination
from backend.models.evidence import Evidence
from backend.models.habitation import Habitation
from backend.models.hazard import Hazard
from backend.models.recommendation import Recommendation
from backend.models.relocation_priority import RelocationPriority
from backend.models.risk_assessment import RiskAssessment
from backend.models.user import User

REQUIRED_TABLES = {
    "users",
    "habitations",
    "hazards",
    "evidence",
    "risk_assessments",
    "relocation_priorities",
    "destinations",
    "capacity_assessments",
    "recommendations",
}


def test_model_imports_and_metadata_registration() -> None:
    assert User.__tablename__ == "users"
    assert Habitation.__tablename__ == "habitations"
    assert Hazard.__tablename__ == "hazards"
    assert Evidence.__tablename__ == "evidence"
    assert RiskAssessment.__tablename__ == "risk_assessments"
    assert RelocationPriority.__tablename__ == "relocation_priorities"
    assert Destination.__tablename__ == "destinations"
    assert CapacityAssessment.__tablename__ == "capacity_assessments"
    assert Recommendation.__tablename__ == "recommendations"

    for table_name in REQUIRED_TABLES:
        assert table_name in Base.metadata.tables
