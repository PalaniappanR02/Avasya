from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_recommendation_confidence_score_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_assessment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("risk_assessments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    destination_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("destinations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    relocation_priority_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("relocation_priorities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recommendation_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    data_origin: Mapped[DataOrigin] = mapped_column(
        SAEnum(DataOrigin, name="data_origin", native_enum=True, validate_strings=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    risk_assessment: Mapped["RiskAssessment"] = relationship(back_populates="recommendations")
    destination: Mapped["Destination"] = relationship(back_populates="recommendations")
    relocation_priority: Mapped["RelocationPriority"] = relationship(back_populates="recommendations")
    approvals: Mapped[list["RecommendationApproval"]] = relationship(
        back_populates="recommendation",
        cascade="all, delete-orphan",
    )
