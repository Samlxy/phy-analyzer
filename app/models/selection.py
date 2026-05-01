from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class Selection(db.Model):
    __tablename__ = "selections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slate_date: Mapped[date] = mapped_column(Date, index=True)
    rank: Mapped[int] = mapped_column(Integer)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), index=True)
    market: Mapped[str] = mapped_column(String(8))
    odds: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|won|lost|void
    graded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
