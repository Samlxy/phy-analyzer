from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from ..extensions import db
from ..models import Fixture, Prediction
from ._serializers import serialize_match_row

bp = Blueprint("analyzer", __name__)


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    return datetime(d.year, d.month, d.day), datetime(d.year, d.month, d.day, 23, 59, 59)


@bp.get("/matches")
def list_matches():
    target_str = request.args.get("date") or date.today().isoformat()
    target = datetime.strptime(target_str, "%Y-%m-%d").date()
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(50, max(1, int(request.args.get("page_size", 20))))

    start, end = _day_bounds(target)
    base = select(Fixture).where(Fixture.kickoff_utc.between(start, end))

    total = db.session.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    rows = list(db.session.execute(
        base.order_by(Fixture.kickoff_utc.asc())
            .offset((page - 1) * page_size).limit(page_size)
    ).scalars())

    if not rows:
        return jsonify(date=target_str, page=page, page_size=page_size, total=0, items=[])

    pred_map = {
        p.fixture_id: p for p in db.session.execute(
            select(Prediction).where(Prediction.fixture_id.in_([fx.id for fx in rows]))
        ).scalars()
    }

    items = [serialize_match_row(fx, pred_map.get(fx.id)) for fx in rows]
    # Sort within page so highest-confidence rows appear first; keep kickoff as secondary.
    items.sort(key=lambda r: (-r["confidence"], r["kickoff"]))

    return jsonify(date=target_str, page=page, page_size=page_size, total=int(total), items=items)
