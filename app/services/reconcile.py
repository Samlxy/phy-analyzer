from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from ..extensions import db
from ..models import Fixture, Selection
from ..providers.base import DataProvider


def _grade(market: str, home: int, away: int) -> str:
    """Return 'won' | 'lost' for the given market against a final score."""
    total = home + away
    if market == "1":
        return "won" if home > away else "lost"
    if market == "2":
        return "won" if away > home else "lost"
    if market == "X":
        return "won" if home == away else "lost"
    if market == "12":
        return "won" if home != away else "lost"
    if market == "O1.5":
        return "won" if total >= 2 else "lost"
    if market == "U3.5":
        return "won" if total <= 3 else "lost"
    return "void"


def reconcile_day(provider: DataProvider, day: date) -> tuple[int, int]:
    """Fetch final scores for pending selections on `day`, grade them, persist.

    Returns (graded, skipped). A selection is skipped if the fixture has no FT score yet.
    """
    pending = list(db.session.execute(
        select(Selection).where(Selection.slate_date == day, Selection.status == "pending")
    ).scalars())
    if not pending:
        return (0, 0)

    fixtures = {
        fx.id: fx for fx in db.session.execute(
            select(Fixture).where(Fixture.id.in_([s.fixture_id for s in pending]))
        ).scalars()
    }

    graded = skipped = 0
    for s in pending:
        fx = fixtures.get(s.fixture_id)
        score: tuple[int, int] | None = None
        if fx and fx.home_goals is not None and fx.away_goals is not None and fx.status == "FT":
            score = (fx.home_goals, fx.away_goals)
        else:
            score = provider.final_score(s.fixture_id)
            if score is not None and fx is not None:
                fx.home_goals, fx.away_goals = score
                fx.status = "FT"

        if score is None:
            skipped += 1
            continue

        s.status = _grade(s.market, score[0], score[1])
        s.graded_at = datetime.utcnow()
        graded += 1

    db.session.commit()
    return (graded, skipped)
