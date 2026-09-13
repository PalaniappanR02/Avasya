from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class HabitationHazard(Base):
    __tablename__ = "habitation_hazards"

    habitation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("habitations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hazard_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("hazards.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    habitation: Mapped["Habitation"] = relationship(
        back_populates="habitation_hazard_links",
        overlaps="hazards",
    )
    hazard: Mapped["Hazard"] = relationship(
        back_populates="habitation_hazard_links",
        overlaps="habitations",
    )
