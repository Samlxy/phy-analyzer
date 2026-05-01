from __future__ import annotations

from datetime import date

from sqlalchemy import select as sa_select

from ..extensions import db
from ..models import Fixture, Prediction, Selection
from ..selector.daily import Candidate, select_daily
from .ingest import fixtures_on


def build_slate(day: date, *, threshold: float, max_picks: int, max_combined: float) -> list[Selection]:
    """Build (and persist) the daily slate from existing Predictions."""
    fixtures = fixtures_on(day)
    fixture_ids = [fx.id for fx in fixtures]
    if not fixture_ids:
        return []

    preds = list(db.session.execute(
        sa_select(Prediction).where(Prediction.fixture_id.in_(fixture_ids))
    ).scalars())

    cands: list[Candidate] = []
    for p in preds:
        market = p.best_market
        odds = (p.odds or {}).get(market, 0.0)
        if odds <= 1.0:
            continue
        cands.append(Candidate(
            fixture_id=p.fixture_id,
            market=market,
            odds=float(odds),
            confidence=float(p.confidence),
        ))

    chosen = select_daily(
        cands,
        max_picks=max_picks,
        max_combined_odds=max_combined,
        min_confidence=threshold,
    )

    # Wipe & rewrite slate for the day (idempotent)
    db.session.execute(
        Selection.__table__.delete().where(Selection.slate_date == day)
    )
    rows: list[Selection] = []
    for rank, c in enumerate(chosen, start=1):
        s = Selection(
            slate_date=day, rank=rank, fixture_id=c.fixture_id,
            market=c.market, odds=c.odds, confidence=c.confidence,
            status="pending",
        )
        db.session.add(s)
        rows.append(s)
    db.session.commit()
    return rows
