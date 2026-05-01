from __future__ import annotations

import numpy as np

MARKETS = ("1", "X", "2", "12", "O1.5", "U3.5")


def market_probabilities(matrix: np.ndarray) -> dict[str, float]:
    """Derive probabilities for the supported popular markets from a score matrix."""
    n = matrix.shape[0]
    idx_i, idx_j = np.indices((n, n))

    p_home = float(matrix[idx_i > idx_j].sum())
    p_draw = float(np.trace(matrix))
    p_away = float(matrix[idx_i < idx_j].sum())
    p_12 = float(p_home + p_away)
    # Over 1.5: total goals >= 2
    p_over_15 = float(matrix[idx_i + idx_j >= 2].sum())
    # Under 3.5: total goals <= 3
    p_under_35 = float(matrix[idx_i + idx_j <= 3].sum())

    return {
        "1": p_home,
        "X": p_draw,
        "2": p_away,
        "12": p_12,
        "O1.5": p_over_15,
        "U3.5": p_under_35,
    }


def best_market(probs: dict[str, float]) -> tuple[str, float]:
    """Pick the highest-probability market as the headline confidence pick."""
    market = max(probs, key=probs.get)
    return market, probs[market]
