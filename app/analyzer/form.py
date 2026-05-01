from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class TeamForm:
    team_id: int
    matches: int
    goals_for_avg: float
    goals_against_avg: float
    home_goals_for_avg: float
    home_goals_against_avg: float
    away_goals_for_avg: float
    away_goals_against_avg: float


def _exp_weights(n: int, half_life: int = 5) -> np.ndarray:
    """Exponential decay weights with newest first."""
    if n <= 0:
        return np.array([])
    decay = np.log(2) / max(1, half_life)
    w = np.exp(-decay * np.arange(n))
    return w / w.sum()


def compute_form(team_id: int, fixtures: list[dict[str, Any]]) -> TeamForm:
    """Compute weighted form metrics from API-Football `fixtures?team=&last=` payload."""
    if not fixtures:
        return TeamForm(team_id, 0, 0, 0, 0, 0, 0, 0)

    gf, ga, h_gf, h_ga, a_gf, a_ga, h_w, a_w = [], [], [], [], [], [], [], []
    weights = _exp_weights(len(fixtures))

    for w, fx in zip(weights, fixtures):
        teams = fx["teams"]; goals = fx["goals"]
        is_home = teams["home"]["id"] == team_id
        scored = goals["home"] if is_home else goals["away"]
        conceded = goals["away"] if is_home else goals["home"]
        if scored is None or conceded is None:
            continue
        gf.append(w * scored); ga.append(w * conceded)
        if is_home:
            h_gf.append(w * scored); h_ga.append(w * conceded); h_w.append(w)
        else:
            a_gf.append(w * scored); a_ga.append(w * conceded); a_w.append(w)

    def _safe(num: list[float], denom: list[float] | None = None) -> float:
        d = sum(denom) if denom else 1.0
        return float(sum(num) / d) if d else 0.0

    return TeamForm(
        team_id=team_id,
        matches=len(fixtures),
        goals_for_avg=_safe(gf),
        goals_against_avg=_safe(ga),
        home_goals_for_avg=_safe(h_gf, h_w),
        home_goals_against_avg=_safe(h_ga, h_w),
        away_goals_for_avg=_safe(a_gf, a_w),
        away_goals_against_avg=_safe(a_ga, a_w),
    )


def expected_goals(home: TeamForm, away: TeamForm, league_avg: float = 1.35) -> tuple[float, float]:
    """Crude attack/defense expected goals.

    λ_home = home.attack_home * away.defense_away * league_avg
    λ_away = away.attack_away * home.defense_home * league_avg
    where attack/defense are normalized by league avg.
    """
    base = max(0.5, league_avg)
    h_attack = (home.home_goals_for_avg or home.goals_for_avg) / base
    h_defense = (home.home_goals_against_avg or home.goals_against_avg) / base
    a_attack = (away.away_goals_for_avg or away.goals_for_avg) / base
    a_defense = (away.away_goals_against_avg or away.goals_against_avg) / base

    lambda_home = max(0.15, h_attack * a_defense * base)
    lambda_away = max(0.15, a_attack * h_defense * base)
    return lambda_home, lambda_away
