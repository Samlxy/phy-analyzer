from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from ..extensions import db
from ..models import Fixture, League, Team
from ..providers.base import DataProvider, FixtureDTO


def _parse_kickoff(iso: str) -> datetime:
    # API-Football returns ISO8601 with timezone offset (e.g. 2026-05-01T14:00:00+00:00)
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _upsert_league(dto: FixtureDTO) -> None:
    lg = db.session.get(League, dto.league_id)
    if lg is None:
        db.session.add(League(id=dto.league_id, name=dto.league_name,
                              country=dto.country or "", logo=dto.league_logo))
    else:
        lg.name = dto.league_name
        lg.country = dto.country or ""
        lg.logo = dto.league_logo


def _upsert_team(team_id: int, name: str, logo: str | None) -> None:
    t = db.session.get(Team, team_id)
    if t is None:
        db.session.add(Team(id=team_id, name=name, logo=logo))
    else:
        t.name = name
        t.logo = logo


def _upsert_fixture(dto: FixtureDTO) -> None:
    fx = db.session.get(Fixture, dto.fixture_id)
    kickoff = _parse_kickoff(dto.kickoff_utc)
    if fx is None:
        fx = Fixture(
            id=dto.fixture_id, league_id=dto.league_id,
            home_id=dto.home_id, away_id=dto.away_id,
            kickoff_utc=kickoff, status=dto.status,
            home_goals=dto.home_goals, away_goals=dto.away_goals,
        )
        db.session.add(fx)
    else:
        fx.league_id = dto.league_id
        fx.home_id = dto.home_id
        fx.away_id = dto.away_id
        fx.kickoff_utc = kickoff
        fx.status = dto.status
        fx.home_goals = dto.home_goals
        fx.away_goals = dto.away_goals


def ingest_fixtures(provider: DataProvider, day: date) -> int:
    """Pull all fixtures for `day`, upsert leagues/teams/fixtures. Returns count."""
    dtos = provider.fixtures_for(day)
    for dto in dtos:
        _upsert_league(dto)
        _upsert_team(dto.home_id, dto.home_name, dto.home_logo)
        _upsert_team(dto.away_id, dto.away_name, dto.away_logo)
        _upsert_fixture(dto)
    db.session.commit()
    return len(dtos)


def fixtures_on(day: date) -> list[Fixture]:
    start = datetime(day.year, day.month, day.day)
    end = datetime(day.year, day.month, day.day, 23, 59, 59)
    return list(
        db.session.execute(
            select(Fixture).where(Fixture.kickoff_utc.between(start, end))
            .order_by(Fixture.kickoff_utc.asc())
        ).scalars()
    )
