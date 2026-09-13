from __future__ import annotations

from typing import Optional
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class Hazard(Base):
    __tablename__ = "hazards"
    __table_args__ = (
        Index("ix_hazards_geom", "geom", postgresql_using="gist"),
        CheckConstraint("severity_score >= 0 AND severity_score <= 100", name="ck_hazards_severity_score_range"),
        CheckConstraint("probability_score >= 0 AND probability_score <= 100", name="ck_hazards_probability_score_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hazard_type: Mapped[str] = mapped_column(String(100), nullable=False)
    hazard_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    severity_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    probability_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    data_origin: Mapped[DataOrigin] = mapped_column(
        SAEnum(DataOrigin, name="data_origin", native_enum=True, validate_strings=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    habitation_hazard_links: Mapped[list["HabitationHazard"]] = relationship(
        back_populates="hazard",
        cascade="all, delete-orphan",
        overlaps="habitations,hazard",
    )
    habitations: Mapped[list["Habitation"]] = relationship(
        secondary="habitation_hazards",
        back_populates="hazards",
        overlaps="habitation_hazard_links,habitation,hazard",
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="hazard",
        cascade="all, delete-orphan",
    )
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="hazard",
        cascade="all, delete-orphan",
    )
