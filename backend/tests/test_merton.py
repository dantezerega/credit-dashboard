import math

import pytest

from app.calculations.merton import pd_to_horizon, solve_merton


def test_converges_and_recovers_equity_value():
    r = solve_merton(equity_value=100e9, equity_volatility=0.30, debt_face=50e9,
                     risk_free_rate=0.04, maturity=1.0)
    assert r.converged
    # Plugging solved (V, sigma_V) back into Black-Scholes must reproduce E.
    from app.calculations.merton import _equity_from_assets
    e = _equity_from_assets(r.asset_value, 50e9, 0.04, r.asset_volatility, 1.0)
    assert e == pytest.approx(100e9, rel=1e-6)


def test_volatility_linkage_holds():
    from app.calculations.mathutils import norm_cdf
    r = solve_merton(equity_value=80e9, equity_volatility=0.35, debt_face=60e9,
                     risk_free_rate=0.045, maturity=1.0)
    implied_sigma_e = (r.asset_value / r.equity_value) * norm_cdf(r.d1) * r.asset_volatility
    assert implied_sigma_e == pytest.approx(0.35, rel=1e-4)


def test_asset_value_between_equity_and_equity_plus_debt():
    r = solve_merton(equity_value=100e9, equity_volatility=0.25, debt_face=40e9,
                     risk_free_rate=0.04, maturity=1.0)
    assert 100e9 < r.asset_value < 100e9 + 40e9


def test_more_leverage_means_higher_pd():
    low = solve_merton(100e9, 0.30, 20e9, 0.04, 1.0)
    high = solve_merton(100e9, 0.30, 120e9, 0.04, 1.0)
    assert high.default_probability > low.default_probability
    assert high.distance_to_default < low.distance_to_default


def test_more_volatility_means_higher_pd():
    calm = solve_merton(100e9, 0.15, 60e9, 0.04, 1.0)
    wild = solve_merton(100e9, 0.60, 60e9, 0.04, 1.0)
    assert wild.default_probability > calm.default_probability


def test_investment_grade_profile_has_small_pd():
    r = solve_merton(equity_value=300e9, equity_volatility=0.20, debt_face=40e9,
                     risk_free_rate=0.04, maturity=1.0)
    assert r.default_probability < 0.001
    assert r.distance_to_default > 3


def test_no_debt_zero_pd():
    r = solve_merton(100e9, 0.3, 0.0, 0.04, 1.0)
    assert r.default_probability == 0.0
    assert math.isinf(r.distance_to_default)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        solve_merton(-1, 0.3, 10, 0.04, 1.0)
    with pytest.raises(ValueError):
        solve_merton(100, -0.3, 10, 0.04, 1.0)
    with pytest.raises(ValueError):
        solve_merton(100, 0.3, 10, 0.04, 0.0)


def test_pd_to_horizon():
    pd5 = 0.10
    pd1 = pd_to_horizon(pd5, 5.0, 1.0)
    assert 0 < pd1 < pd5
    # constant hazard: compounding 1y PD for 5y recovers 5y PD
    assert 1 - (1 - pd1) ** 5 == pytest.approx(pd5, rel=1e-9)
    assert pd_to_horizon(0.0, 5, 1) == 0.0
    assert pd_to_horizon(1.0, 5, 1) == 1.0
