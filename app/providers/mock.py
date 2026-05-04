from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .base import DataProvider, FixtureDTO


def _rand_odds() -> dict[str, float]:
    import random
    return {
        "1": round(random.uniform(1.5, 2.8), 2),
        "X": round(random.uniform(2.8, 4.2), 2),
        "2": round(random.uniform(2.2, 5.5), 2),
        "12": round(random.uniform(1.2, 1.6), 2),
        "O1.5": round(random.uniform(1.15, 1.45), 2),
        "U3.5": round(random.uniform(1.25, 1.75), 2),
    }


def _rand_score() -> tuple[int, int]:
    import random
    return (random.randint(0, 4), random.randint(0, 4))


class MockProvider(DataProvider):
    """In-memory fake provider for development without RapidAPI keys.

    Returns a deterministic set of fixtures for the last 30 days and today.
    All fixtures have fake odds and random final scores.
    """

    def __init__(self, seed: int = 42):
        import random
        random.seed(seed)

    def fixtures_for(self, day: date) -> list[FixtureDTO]:
        # Return 5–8 fixtures per day, spanning a few leagues.
        if day < date.today() - timedelta(days=30) or day > date.today():
            return []
        import random
        n = random.randint(5, 8)
        out = []
        for i in range(n):
            kickoff = datetime.combine(day, datetime.min.time()) + timedelta(hours=13 + i * 2)
            home_goals, away_goals = _rand_score()
            out.append(FixtureDTO(
                fixture_id=100_000 * day.timetuple().tm_yday + i,
                league_id=39 if i % 2 else 140,
                league_name="Premier League" if i % 2 else "La Liga",
                country="England" if i % 2 else "Spain",
                league_logo=None,
                home_id=2000 + i,
                home_name=f"Team H{i}",
                home_logo=None,
                away_id=3000 + i,
                away_name=f"Team A{i}",
                away_logo=None,
                kickoff_utc=kickoff.isoformat() + "Z",
                status="FT",
                home_goals=home_goals,
                away_goals=away_goals,
            ))
        return out

    def team_last_matches(self, team_id: int, n: int = 10) -> list[dict[str, Any]]:
        # Return a few generic past matches.
        return [{"fixture": {"id": 999999, "date": "2026-04-01T12:00:00Z", "status": {"short": "FT"}},
                "goals": {"home": 1, "away": 2},
                "teams": {"home": {"id": 4000 + team_id, "name": f"Opponent {team_id}"}, 
                         "away": {"id": team_id, "name": f"Team {team_id}"}}}
                for _ in range(min(n, 3))]

    def team_matches_before(self, team_id: int, before: date, n: int = 10) -> list[dict[str, Any]]:
        # Same as team_last_matches but filtered before `before`.
        return self.team_last_matches(team_id, n)

    def head_to_head(self, home_id: int, away_id: int, n: int = 5) -> list[dict[str, Any]]:
        return [{"fixture": {"id": 888888, "date": "2026-03-15T15:00:00Z", "status": {"short": "FT"}},
                "goals": {"home": 2, "away": 2},
                "teams": {"home": {"id": home_id, "name": f"Team {home_id}"}, 
                         "away": {"id": away_id, "name": f"Team {away_id}"}}}
                for _ in range(min(n, 3))]

    def odds_for_fixture(self, fixture_id: int) -> dict[str, float]:
        return _rand_odds()

    def final_score(self, fixture_id: int) -> tuple[int, int] | None:
        # In the mock fixtures we already embed final scores, but the reconcile path
        # may call this. Return a deterministic fake score.
        return _rand_score()
