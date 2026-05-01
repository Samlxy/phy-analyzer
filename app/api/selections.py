from __future__ import annotations

from datetime import date, datetime
from math import prod

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..extensions import db
from ..models import Fixture, Selection
from ._serializers import serialize_selection

bp = Blueprint("selections", __name__)


@bp.get("/selections")
def list_selections():
    target_str = request.args.get("date") or date.today().isoformat()
    target = datetime.strptime(target_str, "%Y-%m-%d").date()

    rows = list(db.session.execute(
        select(Selection).where(Selection.slate_date == target).order_by(Selection.rank.asc())
    ).scalars())

    fixtures = {
        fx.id: fx for fx in db.session.execute(
            select(Fixture).where(Fixture.id.in_([s.fixture_id for s in rows] or [-1]))
        ).scalars()
    }

    items = [serialize_selection(s, fixtures.get(s.fixture_id)) for s in rows]
    combined = prod((s.odds for s in rows), start=1.0) if rows else 0.0

    return jsonify(
        date=target_str,
        combined_odds=round(combined, 2),
        stake_suggestion_pct=100,
        items=items,
    )
