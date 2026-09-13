from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import DataOrigin


class RelocationPriority(Base):
    __tablename__ = "relocation_priorities"
    __table_args__ = (
        CheckConstraint("priority_score >= 0 AND priority_score <= 100", name="ck_relocation_priority_score_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    habitation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("habitations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    destination_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("destinations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    priority_score: Mapped[float] = mapped_column(nullable=False)
    priority_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rationale: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
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

    user: Mapped["User"] = relationship(back_populates="relocation_priorities")
    habitation: Mapped["Habitation"] = relationship(back_populates="relocation_priorities")
    destination: Mapped["Destination"] = relationship(back_populates="relocation_priorities")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="relocation_priority",
        cascade="all, delete-orphan",
    )
