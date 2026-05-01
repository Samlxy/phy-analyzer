from __future__ import annotations

from datetime import date
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from .base import DataProvider, FixtureDTO
from .cache import DiskCache


class ApiFootballProvider(DataProvider):
    """RapidAPI-hosted API-Football v3 client.

    Docs: https://www.api-football.com/documentation-v3
    Endpoints used:
        GET /fixtures?date=YYYY-MM-DD
        GET /fixtures?team={id}&last={n}
        GET /fixtures/headtohead?h2h={home}-{away}&last={n}
        GET /odds?fixture={id}&bookmaker=8  (bet365 by default; configurable)
        GET /fixtures?id={id}
    """

    def __init__(self, base_url: str, api_key: str, host: str, timeout: float = 15.0,
                 cache_dir: str | None = "var/cache/api_football"):
        self._client = httpx.Client(
            base_url=base_url,
            headers={"x-rapidapi-key": api_key, "x-rapidapi-host": host},
            timeout=timeout,
        )
        self._cache = DiskCache(cache_dir) if cache_dir else None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=8))
    def _fetch(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        r = self._client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        if self._cache is not None:
            hit = self._cache.get(path, params)
            if hit is not None:
                return hit
        data = self._fetch(path, params)
        if self._cache is not None:
            self._cache.set(path, params, data)
        return data

    # ---- DataProvider impl ------------------------------------------------

    def fixtures_for(self, day: date) -> list[FixtureDTO]:
        data = self._get("/fixtures", {"date": day.isoformat()})
        out: list[FixtureDTO] = []
        for item in data.get("response", []):
            fx = item["fixture"]
            lg = item["league"]
            tm = item["teams"]
            gl = item.get("goals", {})
            out.append(
                FixtureDTO(
                    fixture_id=fx["id"],
                    league_id=lg["id"],
                    league_name=lg["name"],
                    country=lg.get("country", ""),
                    league_logo=lg.get("logo"),
                    kickoff_utc=fx["date"],
                    home_id=tm["home"]["id"],
                    home_name=tm["home"]["name"],
                    home_logo=tm["home"].get("logo"),
                    away_id=tm["away"]["id"],
                    away_name=tm["away"]["name"],
                    away_logo=tm["away"].get("logo"),
                    status=fx["status"]["short"],
                    home_goals=gl.get("home"),
                    away_goals=gl.get("away"),
                )
            )
        return out

    def team_last_matches(self, team_id: int, n: int = 10) -> list[dict[str, Any]]:
        data = self._get("/fixtures", {"team": team_id, "last": n})
        return data.get("response", [])

    def team_matches_before(self, team_id: int, before: date, n: int = 10) -> list[dict[str, Any]]:
        # API-Football supports from/to+season; we use a wide season window ending the day before.
        # Caller code filters to finished matches and trims to the newest `n`.
        season = before.year if before.month >= 7 else before.year - 1
        data = self._get("/fixtures", {
            "team": team_id, "season": season,
            "from": f"{season}-07-01", "to": (before.isoformat()),
        })
        finished = [
            f for f in data.get("response", [])
            if f.get("fixture", {}).get("status", {}).get("short") == "FT"
            and f.get("fixture", {}).get("date", "") < before.isoformat()
        ]
        finished.sort(key=lambda f: f["fixture"]["date"], reverse=True)
        return finished[:n]

    def head_to_head(self, home_id: int, away_id: int, n: int = 5) -> list[dict[str, Any]]:
        data = self._get(
            "/fixtures/headtohead", {"h2h": f"{home_id}-{away_id}", "last": n}
        )
        return data.get("response", [])

    def odds_for_fixture(self, fixture_id: int) -> dict[str, float]:
        data = self._get("/odds", {"fixture": fixture_id})
        result: dict[str, float] = {}
        for entry in data.get("response", []):
            for bk in entry.get("bookmakers", []):
                for bet in bk.get("bets", []):
                    name = bet.get("name", "").lower()
                    values = {v["value"]: float(v["odd"]) for v in bet.get("values", [])}
                    if name == "match winner":
                        result.setdefault("1", values.get("Home", 0.0))
                        result.setdefault("X", values.get("Draw", 0.0))
                        result.setdefault("2", values.get("Away", 0.0))
                    elif name == "double chance":
                        if "Home/Away" in values:
                            result.setdefault("12", values["Home/Away"])
                    elif name == "goals over/under":
                        if "Over 1.5" in values:
                            result.setdefault("O1.5", values["Over 1.5"])
                        if "Under 3.5" in values:
                            result.setdefault("U3.5", values["Under 3.5"])
                if result:
                    break
            if result:
                break
        return result

    def final_score(self, fixture_id: int) -> tuple[int, int] | None:
        data = self._get("/fixtures", {"id": fixture_id})
        resp = data.get("response", [])
        if not resp:
            return None
        item = resp[0]
        if item["fixture"]["status"]["short"] != "FT":
            return None
        gl = item.get("goals", {})
        if gl.get("home") is None or gl.get("away") is None:
            return None
        return int(gl["home"]), int(gl["away"])
