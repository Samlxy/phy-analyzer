from __future__ import annotations

import numpy as np
from scipy.stats import poisson


def score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 8) -> np.ndarray:
    """Independent-Poisson score matrix P[i, j] = P(home=i, away=j)."""
    h = poisson.pmf(np.arange(max_goals + 1), lambda_home)
    a = poisson.pmf(np.arange(max_goals + 1), lambda_away)
    return np.outer(h, a)


def dixon_coles_correction(matrix: np.ndarray, lambda_home: float, lambda_away: float, rho: float = -0.08) -> np.ndarray:
    """Apply Dixon-Coles low-score correlation (only adjusts the 0-0, 1-0, 0-1, 1-1 cells)."""
    m = matrix.copy()
    lh, la = lambda_home, lambda_away
    m[0, 0] *= 1 - lh * la * rho
    m[1, 0] *= 1 + la * rho
    m[0, 1] *= 1 + lh * rho
    m[1, 1] *= 1 - rho
    m /= m.sum()  # renormalize
    return m
