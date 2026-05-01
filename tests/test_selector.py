from app.selector.daily import Candidate, select_daily


def test_selector_respects_caps():
    cands = [
        Candidate(1, "O1.5", 1.22, 0.86),
        Candidate(2, "12",   1.28, 0.81),
        Candidate(3, "U3.5", 1.45, 0.74),
        Candidate(4, "1",    1.85, 0.70),
        Candidate(5, "1",    2.10, 0.66),
        Candidate(6, "X",    3.50, 0.55),  # below threshold
    ]
    picks = select_daily(cands, max_picks=5, max_combined_odds=5.0, min_confidence=0.62)

    assert len(picks) <= 5
    combined = 1.0
    for p in picks:
        combined *= p.odds
    assert combined <= 5.0 + 1e-9
    # No fixture appears twice
    assert len({p.fixture_id for p in picks}) == len(picks)
    # All meet threshold
    assert all(p.confidence >= 0.62 for p in picks)
