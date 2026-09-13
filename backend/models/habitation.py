from __future__ import annotations

from typing import Optional
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class Habitation(Base):
    __tablename__ = "habitations"
    __table_args__ = (
        Index("ix_habitations_user_id", "user_id"),
        Index("ix_habitations_geom", "geom", postgresql_using="gist"),
        CheckConstraint("population >= 0", name="ck_habitations_population_non_negative"),
        CheckConstraint("households >= 0", name="ck_habitations_households_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    village_or_ward: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(nullable=True)
    geom: Mapped[Optional[object]] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )
    population: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    households: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
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

    user: Mapped["User"] = relationship(back_populates="habitations")
    habitation_hazard_links: Mapped[list["HabitationHazard"]] = relationship(
        back_populates="habitation",
        cascade="all, delete-orphan",
    )
    hazards: Mapped[list["Hazard"]] = relationship(
        secondary="habitation_hazards",
        back_populates="habitations",
        overlaps="habitation_hazard_links,habitation,hazard",
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="habitation",
        cascade="all, delete-orphan",
    )
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="habitation",
        cascade="all, delete-orphan",
    )
    relocation_priorities: Mapped[list["RelocationPriority"]] = relationship(
        back_populates="habitation",
        cascade="all, delete-orphan",
    )
    capacity_assessments: Mapped[list["CapacityAssessment"]] = relationship(
        back_populates="habitation",
        cascade="all, delete-orphan",
    )
