from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from ..extensions import db
from ..models import Fixture, Selection

bp = Blueprint("history", __name__)


@bp.get("/history")
def list_history():
    today = date.today()
    frm = datetime.strptime(request.args.get("from") or (today - timedelta(days=14)).isoformat(), "%Y-%m-%d").date()
    to = datetime.strptime(request.args.get("to") or today.isoformat(), "%Y-%m-%d").date()
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(50, max(1, int(request.args.get("page_size", 20))))

    base = select(Selection).where(Selection.slate_date.between(frm, to)).where(Selection.status != "pending")

    total = db.session.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    rows = list(db.session.execute(
        base.order_by(Selection.slate_date.desc(), Selection.rank.asc())
            .offset((page - 1) * page_size).limit(page_size)
    ).scalars())

    fixtures = {
        fx.id: fx for fx in db.session.execute(
            select(Fixture).where(Fixture.id.in_([s.fixture_id for s in rows] or [-1]))
        ).scalars()
    }

    items = []
    for s in rows:
        fx = fixtures.get(s.fixture_id)
        items.append({
            "date": s.slate_date.isoformat(),
            "fixture_id": s.fixture_id,
            "match": f"{fx.home.name} vs {fx.away.name}" if fx and fx.home and fx.away else f"#{s.fixture_id}",
            "market": s.market,
            "odds": float(s.odds),
            "confidence": float(s.confidence),
            "predicted": s.market,
            "actual_score": f"{fx.home_goals}-{fx.away_goals}" if fx and fx.home_goals is not None and fx.away_goals is not None else "—",
            "result": s.status,
        })

    # Summary across the whole window (not just current page)
    all_status = list(db.session.execute(
        select(Selection.status, Selection.odds).where(
            Selection.slate_date.between(frm, to), Selection.status != "pending"
        )
    ))
    won = sum(1 for st, _ in all_status if st == "won")
    lost = sum(1 for st, _ in all_status if st == "lost")
    void = sum(1 for st, _ in all_status if st == "void")
    n = len(all_status)
    hit_rate = (won / n) if n else 0.0
    # crude ROI: each pick assumed unit stake; won returns (odds-1), lost returns -1, void 0.
    roi_pct = 0.0
    if n:
        pnl = sum((float(o) - 1.0) if st == "won" else (-1.0 if st == "lost" else 0.0)
                  for st, o in all_status)
        roi_pct = round(100.0 * pnl / n, 2)

    return jsonify(
        items=items, page=page, page_size=page_size, total=int(total),
        summary={
            "total": n, "won": won, "lost": lost, "void": void,
            "hit_rate": round(hit_rate, 3), "roi_pct": roi_pct,
            "from": frm.isoformat(), "to": to.isoformat(),
        },
    )
