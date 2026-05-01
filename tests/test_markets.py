import numpy as np

from app.analyzer.markets import market_probabilities
from app.analyzer.poisson import dixon_coles_correction, score_matrix


def test_market_probs_sum_consistency():
    m = score_matrix(1.6, 1.1)
    m = dixon_coles_correction(m, 1.6, 1.1)
    p = market_probabilities(m)

    assert abs(p["1"] + p["X"] + p["2"] - 1.0) < 1e-6
    assert abs(p["12"] - (1 - p["X"])) < 1e-6
    assert 0.0 <= p["O1.5"] <= 1.0
    assert 0.0 <= p["U3.5"] <= 1.0
    # Over 1.5 should be high for these lambdas
    assert p["O1.5"] > 0.7


def test_score_matrix_normalized():
    m = score_matrix(1.4, 1.2)
    assert abs(m.sum() - 1.0) < 1e-3  # truncated at max_goals
    assert (m >= 0).all()
