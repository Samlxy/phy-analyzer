from app.services.reconcile import _grade


def test_grade_1x2():
    assert _grade("1", 2, 1) == "won"
    assert _grade("1", 1, 1) == "lost"
    assert _grade("X", 1, 1) == "won"
    assert _grade("X", 2, 1) == "lost"
    assert _grade("2", 0, 3) == "won"
    assert _grade("2", 3, 0) == "lost"


def test_grade_double_chance():
    assert _grade("12", 2, 1) == "won"
    assert _grade("12", 0, 1) == "won"
    assert _grade("12", 1, 1) == "lost"


def test_grade_totals():
    assert _grade("O1.5", 1, 1) == "won"       # 2 goals ≥ 2
    assert _grade("O1.5", 1, 0) == "lost"      # 1 goal
    assert _grade("U3.5", 2, 1) == "won"       # 3 goals ≤ 3
    assert _grade("U3.5", 2, 2) == "lost"      # 4 goals


def test_grade_unknown_market_is_void():
    assert _grade("BTTS", 1, 1) == "void"
