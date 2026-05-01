from __future__ import annotations

from ..models import Fixture, Prediction, Selection

MARKETS = ("1", "X", "2", "12", "O1.5", "U3.5")


def serialize_match_row(fx: Fixture, pred: Prediction | None) -> dict:
    probs = (pred.probabilities if pred else {}) or {}
    odds = (pred.odds if pred else {}) or {}
    best = pred.best_market if pred else max(probs, key=probs.get) if probs else "1"

    markets = {}
    for m in MARKETS:
        markets[m] = {
            "prob": float(probs.get(m, 0.0)),
            "odds": float(odds.get(m, 0.0)),
            "pick": m == best,
        }

    return {
        "fixture_id": fx.id,
        "league": {
            "id": fx.league.id if fx.league else fx.league_id,
            "name": fx.league.name if fx.league else "",
            "country": fx.league.country if fx.league else "",
            "logo": fx.league.logo if fx.league else None,
        },
        "kickoff": fx.kickoff_utc.isoformat() + "Z",
        "home": {"name": fx.home.name if fx.home else "", "logo": fx.home.logo if fx.home else None},
        "away": {"name": fx.away.name if fx.away else "", "logo": fx.away.logo if fx.away else None},
        "markets": markets,
        "best_market": best,
        "confidence": float(pred.confidence) if pred else 0.0,
    }


def serialize_selection(s: Selection, fx: Fixture | None) -> dict:
    return {
        "rank": s.rank,
        "fixture_id": s.fixture_id,
        "match": (
            f"{fx.home.name} vs {fx.away.name}"
            if fx and fx.home and fx.away else f"#{s.fixture_id}"
        ),
        "league": fx.league.name if fx and fx.league else "",
        "kickoff": (fx.kickoff_utc.isoformat() + "Z") if fx else "",
        "market": s.market,
        "odds": float(s.odds),
        "confidence": float(s.confidence),
        "status": s.status,
    }
