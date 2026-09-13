from __future__ import annotations

from typing import Optional
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class Destination(Base):
    __tablename__ = "destinations"
    __table_args__ = (
        Index("ix_destinations_geom", "geom", postgresql_using="gist"),
        CheckConstraint("capacity_total >= 0", name="ck_destinations_capacity_total_non_negative"),
        CheckConstraint("capacity_available >= 0", name="ck_destinations_capacity_available_non_negative"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_destinations_risk_score_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    capacity_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    capacity_available: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    risk_score: Mapped[Optional[float]] = mapped_column(nullable=True)
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

    relocation_priorities: Mapped[list["RelocationPriority"]] = relationship(
        back_populates="destination",
    )
    capacity_assessments: Mapped[list["CapacityAssessment"]] = relationship(
        back_populates="destination",
        cascade="all, delete-orphan",
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="destination",
        cascade="all, delete-orphan",
    )
    recommendation_approvals: Mapped[list["RecommendationApproval"]] = relationship(
        back_populates="final_destination",
        cascade="all, delete-orphan",
    )
