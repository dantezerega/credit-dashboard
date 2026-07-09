import pytest

from app.calculations.relative_value import (
    CHEAP_Z_THRESHOLD,
    classify,
    fair_spread,
    liquidity_premium,
    rating_from_pd,
    rating_from_spread,
    score_universe,
)


def test_rating_from_spread_bands():
    assert rating_from_spread(0.0040) == "AAA"   # 40bps
    assert rating_from_spread(0.0095) == "A"     # 95bps
    assert rating_from_spread(0.0160) == "BBB"   # 160bps
    assert rating_from_spread(0.0390) == "BB-"   # 390bps (matches CVNA-style HY)
    assert rating_from_spread(0.1500) == "CCC"


def test_rating_from_pd_monotone():
    assert rating_from_pd(0.0001) == "AAA"
    assert rating_from_pd(0.004) == "BBB+"
    assert rating_from_pd(0.06) == "BB-"
    assert rating_from_pd(0.5) == "CCC"
    # ordering: higher PD never maps to a better bucket
    ladder = ["AAA", "AA", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "CCC"]
    prev = -1
    for pd in [0.0001, 0.0004, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5]:
        idx = ladder.index(rating_from_pd(pd))
        assert idx >= prev
        prev = idx


def test_fair_spread_components_sum():
    fs = fair_spread(merton_pd=0.02, maturity=5.0, liquidity_score=70, sector="Energy", rating="BBB")
    total = fs.default_component + fs.liquidity_premium + fs.sector_premium + fs.rating_premium
    assert fs.fair_spread == pytest.approx(total)
    assert fs.default_component > 0
    assert fs.sector_premium == pytest.approx(0.0030)  # Energy = 30bps
    assert fs.rating_premium == pytest.approx(0.0035)  # BBB = 35bps


def test_higher_pd_wider_fair_spread():
    low = fair_spread(0.005, 5.0, 80, "Technology", "A")
    high = fair_spread(0.05, 5.0, 80, "Technology", "A")
    assert high.fair_spread > low.fair_spread


def test_liquidity_premium_bounds():
    assert liquidity_premium(100) == pytest.approx(0.0)
    assert liquidity_premium(0) == pytest.approx(0.0060)
    assert liquidity_premium(50) == pytest.approx(0.0030)
    assert liquidity_premium(-10) == liquidity_premium(0)  # clamped


def test_unknown_sector_and_rating_use_defaults():
    fs = fair_spread(0.01, 5.0, 50, "Unknown Sector", "XYZ")
    assert fs.sector_premium == pytest.approx(0.0015)
    assert fs.rating_premium == pytest.approx(0.0100)


def test_classify_thresholds():
    assert classify(CHEAP_Z_THRESHOLD + 0.01) == "cheap"
    assert classify(-CHEAP_Z_THRESHOLD - 0.01) == "rich"
    assert classify(0.0) == "fair"


def test_score_universe_z_scores_and_labels():
    residuals = {"WIDE": 0.0100, "MID1": 0.0000, "MID2": 0.0002, "MID3": -0.0002, "TIGHT": -0.0100}
    scores = score_universe(residuals)
    assert scores["WIDE"].label == "cheap"
    assert scores["TIGHT"].label == "rich"
    assert scores["MID1"].label == "fair"
    assert scores["WIDE"].z_score > 0 > scores["TIGHT"].z_score
    # z-scores of a cross-section have mean ~0
    assert sum(s.z_score for s in scores.values()) == pytest.approx(0.0, abs=1e-9)


def test_score_universe_percentiles():
    residuals = {f"B{i}": i * 0.001 for i in range(11)}
    scores = score_universe(residuals)
    assert scores["B0"].percentile == pytest.approx(0.0)
    assert scores["B10"].percentile == pytest.approx(100.0)
    assert scores["B5"].percentile == pytest.approx(50.0)


def test_score_universe_edge_cases():
    assert score_universe({}) == {}
    single = score_universe({"ONLY": 0.005})
    assert single["ONLY"].z_score == 0.0
    assert single["ONLY"].label == "fair"
    # identical residuals: no dispersion, all fair
    same = score_universe({"A": 0.001, "B": 0.001, "C": 0.001})
    assert all(s.label == "fair" for s in same.values())
