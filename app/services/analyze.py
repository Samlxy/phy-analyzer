from __future__ import annotations

from datetime import date

from ..analyzer.pipeline import predict_fixture
from ..extensions import db
from ..models import Fixture, Prediction
from ..providers.base import DataProvider
from .ingest import fixtures_on


def analyze_day(provider: DataProvider, day: date) -> int:
    fixtures = fixtures_on(day)
    n = 0
    for fx in fixtures:
        try:
            pred = predict_fixture(provider, fx.id, fx.home_id, fx.away_id)
        except Exception as e:  # one bad fixture shouldn't tank the batch
            print(f"  ! prediction failed for fixture {fx.id}: {e}")
            continue

        existing = db.session.get(Prediction, _existing_prediction_id(fx.id))
        if existing is None:
            db.session.add(Prediction(
                fixture_id=fx.id,
                lambda_home=pred.lambda_home,
                lambda_away=pred.lambda_away,
                probabilities=pred.probabilities,
                odds=pred.odds,
                best_market=pred.best_market,
                confidence=pred.confidence,
            ))
        else:
            existing.lambda_home = pred.lambda_home
            existing.lambda_away = pred.lambda_away
            existing.probabilities = pred.probabilities
            existing.odds = pred.odds
            existing.best_market = pred.best_market
            existing.confidence = pred.confidence
        n += 1
    db.session.commit()
    return n


def _existing_prediction_id(fixture_id: int) -> int | None:
    from sqlalchemy import select
    row = db.session.execute(
        select(Prediction.id).where(Prediction.fixture_id == fixture_id)
    ).first()
    return row[0] if row else None
