from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class FixtureDTO:
    fixture_id: int
    league_id: int
    league_name: str
    country: str
    league_logo: str | None
    kickoff_utc: str
    home_id: int
    home_name: str
    home_logo: str | None
    away_id: int
    away_name: str
    away_logo: str | None
    status: str  # NS, FT, etc.
    home_goals: int | None = None
    away_goals: int | None = None


class DataProvider(ABC):
    """Provider-agnostic interface so the rest of the app never depends on RapidAPI directly."""

    @abstractmethod
    def fixtures_for(self, day: date) -> list[FixtureDTO]: ...

    @abstractmethod
    def team_last_matches(self, team_id: int, n: int = 10) -> list[dict[str, Any]]: ...

    @abstractmethod
    def team_matches_before(self, team_id: int, before: date, n: int = 10) -> list[dict[str, Any]]:
        """Return the last `n` finished matches a team played strictly before `before`.

        Required by the backtest runner to avoid lookahead bias: when predicting
        a match on date D, form must be computed from games played in [D-range, D).
        """

    @abstractmethod
    def head_to_head(self, home_id: int, away_id: int, n: int = 5) -> list[dict[str, Any]]: ...

    @abstractmethod
    def odds_for_fixture(self, fixture_id: int) -> dict[str, float]:
        """Return mapping like {'1': 1.85, 'X': 3.6, '2': 4.2, '12': 1.28, 'O1.5': 1.22, 'U3.5': 1.45}."""

    @abstractmethod
    def final_score(self, fixture_id: int) -> tuple[int, int] | None: ...
