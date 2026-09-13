from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class RecommendationApproval(Base):
    __tablename__ = "recommendation_approvals"
    __table_args__ = (
        CheckConstraint("action IN ('APPROVED', 'REJECTED', 'OVERRIDDEN')", name="ck_recommendation_approvals_action"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    officer_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        SAEnum(
            "APPROVED",
            "REJECTED",
            "OVERRIDDEN",
            name="recommendation_action",
            validate_strings=True,
        ),
        nullable=False,
    )
    original_recommendation: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    final_destination_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("destinations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    override_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_origin: Mapped[DataOrigin] = mapped_column(
        SAEnum(DataOrigin, name="data_origin", native_enum=True, validate_strings=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    recommendation: Mapped["Recommendation"] = relationship(back_populates="approvals")
    officer_user: Mapped["User"] = relationship(back_populates="recommendation_approvals")
    final_destination: Mapped["Destination"] = relationship(back_populates="recommendation_approvals")
