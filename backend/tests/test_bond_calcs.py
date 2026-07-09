import pytest

from app.calculations.bond import (
    build_cashflows,
    convexity,
    g_spread,
    market_implied_pd,
    modified_duration,
    oas,
    price_from_yield,
    price_from_zero_curve,
    spread_from_pd,
    yield_from_price,
    z_spread,
)
from app.calculations.treasury import bootstrap_zero_curve

CURVE = bootstrap_zero_curve({0.5: 0.04, 1: 0.04, 2: 0.04, 5: 0.04, 10: 0.04, 30: 0.04})


def test_cashflow_schedule():
    flows = build_cashflows(0.05, 2.0)
    assert len(flows) == 4
    assert flows[-1].amount == pytest.approx(102.5)  # coupon + principal
    assert all(cf.amount == pytest.approx(2.5) for cf in flows[:-1])
    assert flows[-1].time == pytest.approx(2.0)


def test_par_bond_prices_at_par():
    flows = build_cashflows(0.05, 10.0)
    assert price_from_yield(flows, 0.05) == pytest.approx(100.0, abs=1e-9)


def test_yield_price_roundtrip():
    flows = build_cashflows(0.045, 7.0)
    price = price_from_yield(flows, 0.062)
    assert yield_from_price(flows, price) == pytest.approx(0.062, abs=1e-8)


def test_premium_and_discount():
    flows = build_cashflows(0.06, 5.0)
    assert price_from_yield(flows, 0.04) > 100  # coupon above yield -> premium
    assert price_from_yield(flows, 0.08) < 100


def test_duration_increases_with_maturity():
    short = build_cashflows(0.05, 2.0)
    long = build_cashflows(0.05, 10.0)
    assert modified_duration(long, 0.05) > modified_duration(short, 0.05)


def test_duration_approximates_price_sensitivity():
    flows = build_cashflows(0.05, 10.0)
    y, dy = 0.05, 1e-4
    p0 = price_from_yield(flows, y)
    p1 = price_from_yield(flows, y + dy)
    dur = modified_duration(flows, y)
    assert (p0 - p1) / p0 / dy == pytest.approx(dur, rel=1e-2)


def test_convexity_positive_and_improves_estimate():
    flows = build_cashflows(0.05, 10.0)
    y = 0.05
    cx = convexity(flows, y)
    assert cx > 0
    dy = 0.01
    p0 = price_from_yield(flows, y)
    p1 = price_from_yield(flows, y + dy)
    dur = modified_duration(flows, y)
    est_dur_only = p0 * (1 - dur * dy)
    est_with_cx = p0 * (1 - dur * dy + 0.5 * cx * dy * dy)
    assert abs(est_with_cx - p1) < abs(est_dur_only - p1)


def test_z_spread_zero_for_treasury_priced_bond():
    flows = build_cashflows(0.05, 5.0)
    price = price_from_zero_curve(flows, CURVE, 0.0)
    assert z_spread(flows, price, CURVE) == pytest.approx(0.0, abs=1e-8)


def test_z_spread_roundtrip():
    flows = build_cashflows(0.05, 7.0)
    price = price_from_zero_curve(flows, CURVE, 0.0175)
    assert z_spread(flows, price, CURVE) == pytest.approx(0.0175, abs=1e-8)


def test_wider_spread_lower_price():
    flows = build_cashflows(0.05, 7.0)
    assert price_from_zero_curve(flows, CURVE, 0.02) < price_from_zero_curve(flows, CURVE, 0.01)


def test_g_spread():
    # flat 4% curve: bond yielding 5.5% has ~150bps g-spread
    assert g_spread(0.055, 10.0, CURVE) == pytest.approx(0.015, abs=5e-4)


def test_oas_equals_z_spread_for_bullets():
    flows = build_cashflows(0.05, 5.0)
    price = price_from_zero_curve(flows, CURVE, 0.012)
    assert oas(flows, price, CURVE) == pytest.approx(z_spread(flows, price, CURVE))
    assert oas(flows, price, CURVE, option_cost=0.002) == pytest.approx(
        z_spread(flows, price, CURVE) - 0.002
    )


def test_implied_pd_spread_roundtrip():
    pd = market_implied_pd(0.02, 5.0, 0.40)
    assert 0 < pd < 1
    assert spread_from_pd(pd, 5.0, 0.40) == pytest.approx(0.02, rel=1e-9)


def test_implied_pd_monotone_in_spread():
    assert market_implied_pd(0.03, 5, 0.4) > market_implied_pd(0.01, 5, 0.4)
    # lower recovery -> same spread implies lower PD
    assert market_implied_pd(0.02, 5, 0.0) < market_implied_pd(0.02, 5, 0.6)
