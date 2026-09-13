from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        CheckConstraint("char_length(email) > 0", name="ck_users_email_not_empty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
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

    habitations: Mapped[list["Habitation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="assessor_user",
        foreign_keys="RiskAssessment.assessor_user_id",
    )
    relocation_priorities: Mapped[list["RelocationPriority"]] = relationship(
        back_populates="user",
    )
    capacity_assessments: Mapped[list["CapacityAssessment"]] = relationship(
        back_populates="assessed_by_user",
        foreign_keys="CapacityAssessment.assessed_by_user_id",
    )
    recommendation_approvals: Mapped[list["RecommendationApproval"]] = relationship(
        back_populates="officer_user",
        cascade="all, delete-orphan",
    )
