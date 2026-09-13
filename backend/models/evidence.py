from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        Index("ix_evidence_habitation_id", "habitation_id"),
        Index("ix_evidence_hazard_id", "hazard_id"),
        Index("ix_evidence_risk_assessment_id", "risk_assessment_id"),
        CheckConstraint("char_length(source_name) > 0", name="ck_evidence_source_name_not_empty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    habitation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("habitations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hazard_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("hazards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    risk_assessment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("risk_assessments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    evidence_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    external_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_origin: Mapped[DataOrigin] = mapped_column(
        SAEnum(DataOrigin, name="data_origin", native_enum=True, validate_strings=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    habitation: Mapped["Habitation"] = relationship(back_populates="evidence")
    hazard: Mapped["Hazard"] = relationship(back_populates="evidence")
    risk_assessment: Mapped["RiskAssessment"] = relationship(back_populates="evidence")
