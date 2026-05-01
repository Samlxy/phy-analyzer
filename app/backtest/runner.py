from __future__ import annotations

"""Backtest harness: replay a historical date range and evaluate the model.

Runs entirely against the provider's cached endpoints so repeated sweeps are free.
Does NOT touch the live DB — backtests are pure and write only a JSON report.
"""

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from math import prod
from typing import Iterable

from ..analyzer.form import compute_form, expected_goals
from ..analyzer.markets import best_market, market_probabilities
from ..analyzer.poisson import dixon_coles_correction, score_matrix
from ..providers.base import DataProvider, FixtureDTO
from ..selector.daily import Candidate, select_daily
from ..services.reconcile import _grade


@dataclass
class PickResult:
    date: str
    fixture_id: int
    home: str
    away: str
    market: str
    odds: float
    confidence: float
    home_goals: int
    away_goals: int
    result: str  # won | lost | void


@dataclass
class BacktestReport:
    frm: str
    to: str
    threshold: float
    max_picks: int
    max_combined: float
    total_days: int
    total_picks: int
    won: int
    lost: int
    void: int
    hit_rate: float
    roi_pct: float
    picks: list[PickResult]

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _daterange(frm: date, to: date) -> Iterable[date]:
    d = frm
    while d <= to:
        yield d
        d += timedelta(days=1)


def _predict_offline(provider: DataProvider, fx: FixtureDTO, day: date) -> Candidate | None:
    """Run form→Poisson→markets using only data strictly before `day`."""
    home_hist = provider.team_matches_before(fx.home_id, day, n=10)
    away_hist = provider.team_matches_before(fx.away_id, day, n=10)
    if not home_hist or not away_hist:
        return None

    hf = compute_form(fx.home_id, home_hist)
    af = compute_form(fx.away_id, away_hist)
    lh, la = expected_goals(hf, af)
    matrix = dixon_coles_correction(score_matrix(lh, la), lh, la)
    probs = market_probabilities(matrix)
    market, conf = best_market(probs)

    odds = {}
    try:
        odds = provider.odds_for_fixture(fx.fixture_id)
    except Exception:
        pass
    o = float(odds.get(market, 0.0))
    if o <= 1.0:
        return None

    return Candidate(fixture_id=fx.fixture_id, market=market, odds=o, confidence=conf)


def run_backtest(
    provider: DataProvider,
    frm: date,
    to: date,
    *,
    threshold: float,
    max_picks: int,
    max_combined: float,
) -> BacktestReport:
    picks: list[PickResult] = []
    won = lost = void = 0
    total_days = 0
    pnl_units = 0.0

    for day in _daterange(frm, to):
        total_days += 1
        fixtures = provider.fixtures_for(day)
        # Restrict to matches that actually finished — we need a ground-truth score.
        ft = [fx for fx in fixtures if fx.status == "FT"
              and fx.home_goals is not None and fx.away_goals is not None]

        candidates: list[tuple[Candidate, FixtureDTO]] = []
        for fx in ft:
            c = _predict_offline(provider, fx, day)
            if c is not None:
                candidates.append((c, fx))

        chosen = select_daily(
            [c for c, _ in candidates],
            max_picks=max_picks, max_combined_odds=max_combined, min_confidence=threshold,
        )
        chosen_ids = {c.fixture_id for c in chosen}
        for c, fx in candidates:
            if c.fixture_id not in chosen_ids:
                continue
            result = _grade(c.market, fx.home_goals or 0, fx.away_goals or 0)
            picks.append(PickResult(
                date=day.isoformat(), fixture_id=fx.fixture_id,
                home=fx.home_name, away=fx.away_name,
                market=c.market, odds=c.odds, confidence=c.confidence,
                home_goals=fx.home_goals or 0, away_goals=fx.away_goals or 0,
                result=result,
            ))
            if result == "won":
                won += 1; pnl_units += (c.odds - 1.0)
            elif result == "lost":
                lost += 1; pnl_units -= 1.0
            else:
                void += 1

    total_picks = won + lost + void
    hit_rate = (won / total_picks) if total_picks else 0.0
    roi_pct = round(100.0 * pnl_units / total_picks, 2) if total_picks else 0.0

    return BacktestReport(
        frm=frm.isoformat(), to=to.isoformat(),
        threshold=threshold, max_picks=max_picks, max_combined=max_combined,
        total_days=total_days, total_picks=total_picks,
        won=won, lost=lost, void=void,
        hit_rate=round(hit_rate, 4), roi_pct=roi_pct,
        picks=picks,
    )


def sweep_threshold(
    provider: DataProvider, frm: date, to: date,
    *, thresholds: list[float], max_picks: int, max_combined: float,
) -> list[BacktestReport]:
    """Run the same window across multiple thresholds; pick the best ROI point."""
    return [
        run_backtest(provider, frm, to,
                     threshold=t, max_picks=max_picks, max_combined=max_combined)
        for t in thresholds
    ]
