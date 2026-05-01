from __future__ import annotations

from dataclasses import dataclass
from math import prod


@dataclass
class Candidate:
    fixture_id: int
    market: str
    odds: float
    confidence: float


def select_daily(
    candidates: list[Candidate],
    *,
    max_picks: int = 5,
    max_combined_odds: float = 5.0,
    min_confidence: float = 0.62,
) -> list[Candidate]:
    """Greedy selection of ≤ `max_picks` picks whose combined odds are ≤ `max_combined_odds`,
    maximizing confidence, preferring at most one pick per fixture.
    """
    pool = [c for c in candidates if c.confidence >= min_confidence and c.odds > 1.0]
    pool.sort(key=lambda c: (c.confidence, -c.odds), reverse=True)

    chosen: list[Candidate] = []
    used_fixtures: set[int] = set()

    for cand in pool:
        if cand.fixture_id in used_fixtures:
            continue
        trial = chosen + [cand]
        if len(trial) > max_picks:
            break
        if prod(c.odds for c in trial) > max_combined_odds:
            continue
        chosen.append(cand)
        used_fixtures.add(cand.fixture_id)
        if len(chosen) == max_picks:
            break

    return chosen
