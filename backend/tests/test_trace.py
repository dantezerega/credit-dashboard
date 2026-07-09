from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.calculations.trace import compute_trace_metrics, liquidity_score_proxy


def test_liquidity_proxy_bounds_and_monotonicity():
    small = liquidity_score_proxy(100_000, 0.001)
    big = liquidity_score_proxy(10_000_000, 0.5)
    assert 0 <= small < big <= 100
    assert liquidity_score_proxy(0, 0) == pytest.approx(20.0)  # base only
    assert liquidity_score_proxy(1e9, 10) == pytest.approx(100.0)  # capped


@dataclass
class T:
    price: float
    size: float
    side: str
    trade_date: date


AS_OF = date(2026, 7, 7)


def make_active_tape() -> list[T]:
    trades = []
    for i in range(30):
        d = AS_OF - timedelta(days=i)
        trades.append(T(price=99.5, size=500_000, side="S", trade_date=d))  # dealer sells @ offer
        trades.append(T(price=99.1, size=400_000, side="B", trade_date=d))  # dealer buys @ bid
        trades.append(T(price=99.3, size=250_000, side="D", trade_date=d))
    return trades


def test_vwap():
    trades = [
        T(price=100.0, size=1_000_000, side="S", trade_date=AS_OF),
        T(price=98.0, size=1_000_000, side="B", trade_date=AS_OF),
    ]
    m = compute_trace_metrics(trades, AS_OF)
    assert m.vwap == pytest.approx(99.0)


def test_median_size_and_volume():
    m = compute_trace_metrics(make_active_tape(), AS_OF)
    assert m.median_trade_size == pytest.approx(400_000)
    assert m.total_volume > 0
    assert m.trade_count == len([t for t in make_active_tape() if t.trade_date >= AS_OF - timedelta(days=30)])


def test_bid_ask_proxy():
    m = compute_trace_metrics(make_active_tape(), AS_OF)
    # offer 99.5 vs bid 99.1 -> ~40c on ~99.3 = ~40bps
    assert m.bid_ask_proxy_bps == pytest.approx(40, abs=3)


def test_daily_spread_dispersion():
    m = compute_trace_metrics(make_active_tape(), AS_OF)
    assert m.avg_daily_spread_bps == pytest.approx((99.5 - 99.1) / m.vwap * 10_000, rel=0.05)


def test_active_bond_not_stale_and_liquid():
    m = compute_trace_metrics(make_active_tape(), AS_OF)
    assert not m.is_stale
    assert m.days_since_last_trade == 0
    assert m.liquidity_score > 50


def test_stale_bond_detected():
    old = [T(price=98.0, size=200_000, side="B", trade_date=AS_OF - timedelta(days=20))]
    m = compute_trace_metrics(old, AS_OF)
    assert m.is_stale
    assert m.days_since_last_trade == 20
    assert m.liquidity_score < 30


def test_no_trades_at_all():
    m = compute_trace_metrics([], AS_OF)
    assert m.trade_count == 0
    assert m.is_stale
    assert m.liquidity_score == 0.0
    assert m.vwap is None
    assert m.days_since_last_trade is None


def test_no_trades_in_window_but_older_exist():
    old = [T(price=98.0, size=200_000, side="B", trade_date=AS_OF - timedelta(days=90))]
    m = compute_trace_metrics(old, AS_OF)
    assert m.trade_count == 0
    assert m.days_since_last_trade == 90
    assert m.is_stale


def test_liquid_scores_higher_than_illiquid():
    liquid = compute_trace_metrics(make_active_tape(), AS_OF)
    illiquid = compute_trace_metrics(
        [T(price=99.0, size=25_000, side="B", trade_date=AS_OF - timedelta(days=4))], AS_OF
    )
    assert liquid.liquidity_score > illiquid.liquidity_score
