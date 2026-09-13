from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        Index("ix_risk_assessments_habitation_id", "habitation_id"),
        Index("ix_risk_assessments_hazard_id", "hazard_id"),
        Index("ix_risk_assessments_assessor_user_id", "assessor_user_id"),
        CheckConstraint("overall_risk_score >= 0 AND overall_risk_score <= 100", name="ck_risk_assessment_score_range"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_risk_assessment_confidence_range"),
        CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_risk_assessment_risk_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    habitation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("habitations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hazard_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("hazards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assessor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    overall_risk_score: Mapped[float] = mapped_column(nullable=False)
    risk_level: Mapped[str] = mapped_column(
        SAEnum("LOW", "MEDIUM", "HIGH", name="risk_level", validate_strings=True),
        nullable=False,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    calculation_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    input_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    normalized_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    weights: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    contributions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reasons: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    warnings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    freshness: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    data_quality: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    data_origin: Mapped[DataOrigin] = mapped_column(
        SAEnum(DataOrigin, name="data_origin", native_enum=True, validate_strings=True),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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

    habitation: Mapped["Habitation"] = relationship(back_populates="risk_assessments")
    hazard: Mapped["Hazard"] = relationship(back_populates="risk_assessments")
    assessor_user: Mapped["User"] = relationship(back_populates="risk_assessments", foreign_keys=[assessor_user_id])
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="risk_assessment",
        cascade="all, delete-orphan",
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="risk_assessment",
        cascade="all, delete-orphan",
    )
