from __future__ import annotations

from dataclasses import dataclass

from ..providers.base import DataProvider
from .form import compute_form, expected_goals
from .markets import best_market, market_probabilities
from .poisson import dixon_coles_correction, score_matrix


@dataclass
class FixturePrediction:
    fixture_id: int
    lambda_home: float
    lambda_away: float
    probabilities: dict[str, float]
    odds: dict[str, float]
    best_market: str
    confidence: float


def predict_fixture(provider: DataProvider, fixture_id: int, home_id: int, away_id: int) -> FixturePrediction:
    home_last = provider.team_last_matches(home_id, n=10)
    away_last = provider.team_last_matches(away_id, n=10)

    home_form = compute_form(home_id, home_last)
    away_form = compute_form(away_id, away_last)

    lh, la = expected_goals(home_form, away_form)
    matrix = dixon_coles_correction(score_matrix(lh, la), lh, la)
    probs = market_probabilities(matrix)

    odds: dict[str, float] = {}
    try:
        odds = provider.odds_for_fixture(fixture_id)
    except Exception:
        # Odds are optional; predictions still valid without them.
        odds = {}

    market, conf = best_market(probs)
    return FixturePrediction(
        fixture_id=fixture_id,
        lambda_home=lh,
        lambda_away=la,
        probabilities=probs,
        odds=odds,
        best_market=market,
        confidence=conf,
    )
