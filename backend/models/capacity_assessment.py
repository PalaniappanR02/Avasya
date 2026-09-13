from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class CapacityAssessment(Base):
    __tablename__ = "capacity_assessments"
    __table_args__ = (
        CheckConstraint("nominal_capacity >= 0", name="ck_capacity_assessment_nominal_capacity_non_negative"),
        CheckConstraint("existing_occupancy >= 0", name="ck_capacity_assessment_existing_occupancy_non_negative"),
        CheckConstraint("required_capacity >= 0", name="ck_capacity_assessment_required_capacity_non_negative"),
        CheckConstraint("usable_capacity >= 0", name="ck_capacity_assessment_usable_capacity_non_negative"),
        CheckConstraint("water_constraint >= 0 AND water_constraint <= 100", name="ck_capacity_assessment_water_constraint_range"),
        CheckConstraint("sanitation_constraint >= 0 AND sanitation_constraint <= 100", name="ck_capacity_assessment_sanitation_constraint_range"),
        CheckConstraint("safety_reserve >= 0", name="ck_capacity_assessment_safety_reserve_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    destination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("destinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    habitation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("habitations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessed_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    nominal_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    existing_occupancy: Mapped[int] = mapped_column(Integer, nullable=False)
    water_constraint: Mapped[Optional[float]] = mapped_column(nullable=True)
    sanitation_constraint: Mapped[Optional[float]] = mapped_column(nullable=True)
    safety_reserve: Mapped[Optional[float]] = mapped_column(nullable=True)
    required_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    usable_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity_gap: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    assessment_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
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

    destination: Mapped["Destination"] = relationship(back_populates="capacity_assessments")
    habitation: Mapped["Habitation"] = relationship(back_populates="capacity_assessments")
    assessed_by_user: Mapped["User"] = relationship(back_populates="capacity_assessments", foreign_keys=[assessed_by_user_id])
