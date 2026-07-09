"""TRACE trade tape processing: liquidity metrics, VWAP, bid/ask proxy,
stale pricing detection.

Input is a list of trades: dicts or objects with price, size, side
('B' dealer buy / 'S' dealer sell / 'D' inter-dealer), and trade_date.
"""

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol


class TradeLike(Protocol):
    price: float
    size: float
    side: str
    trade_date: date


@dataclass(frozen=True)
class TraceMetrics:
    trade_count: int
    trades_per_day: float
    vwap: float | None
    median_trade_size: float | None
    total_volume: float
    bid_ask_proxy_bps: float | None  # dealer sell VWAP minus dealer buy VWAP, in bps of price
    avg_daily_spread_bps: float | None  # mean daily high-low price dispersion, bps
    days_since_last_trade: int | None
    is_stale: bool
    liquidity_score: float  # 0 (illiquid) .. 100 (very liquid)


def _vwap(trades: list[TradeLike]) -> float | None:
    vol = sum(t.size for t in trades)
    if vol <= 0:
        return None
    return sum(t.price * t.size for t in trades) / vol


def compute_trace_metrics(
    trades: list[TradeLike],
    as_of: date,
    window_days: int = 30,
    stale_threshold_days: int = 5,
) -> TraceMetrics:
    window_start = as_of - timedelta(days=window_days)
    recent = [t for t in trades if window_start <= t.trade_date <= as_of]

    if not recent:
        last = max((t.trade_date for t in trades), default=None)
        days_since = (as_of - last).days if last else None
        return TraceMetrics(
            trade_count=0, trades_per_day=0.0, vwap=None, median_trade_size=None,
            total_volume=0.0, bid_ask_proxy_bps=None, avg_daily_spread_bps=None,
            days_since_last_trade=days_since, is_stale=True, liquidity_score=0.0,
        )

    vwap = _vwap(recent)
    sizes = [t.size for t in recent]
    median_size = statistics.median(sizes)
    total_volume = sum(sizes)
    trades_per_day = len(recent) / window_days

    # Bid/ask proxy: customer buys print at the offer (dealer sells, side 'S'),
    # customer sells at the bid (dealer buys, side 'B').
    buys = [t for t in recent if t.side == "S"]
    sells = [t for t in recent if t.side == "B"]
    bid_ask_bps: float | None = None
    vb, vs = _vwap(buys), _vwap(sells)
    if vb is not None and vs is not None and vwap:
        bid_ask_bps = max((vb - vs) / vwap * 10_000, 0.0)

    # Daily price dispersion (high - low within each trading day).
    by_day: dict[date, list[float]] = {}
    for t in recent:
        by_day.setdefault(t.trade_date, []).append(t.price)
    daily_ranges = [
        (max(px) - min(px)) / vwap * 10_000 for px in by_day.values() if len(px) >= 2 and vwap
    ]
    avg_daily_spread_bps = statistics.mean(daily_ranges) if daily_ranges else None

    last_trade = max(t.trade_date for t in recent)
    days_since = (as_of - last_trade).days
    is_stale = days_since > stale_threshold_days

    score = liquidity_score(
        trades_per_day=trades_per_day,
        median_trade_size=median_size,
        bid_ask_proxy_bps=bid_ask_bps,
        days_since_last_trade=days_since,
        distinct_trade_days=len(by_day),
        window_days=window_days,
    )

    return TraceMetrics(
        trade_count=len(recent),
        trades_per_day=trades_per_day,
        vwap=vwap,
        median_trade_size=median_size,
        total_volume=total_volume,
        bid_ask_proxy_bps=bid_ask_bps,
        avg_daily_spread_bps=avg_daily_spread_bps,
        days_since_last_trade=days_since,
        is_stale=is_stale,
        liquidity_score=score,
    )


def liquidity_score_proxy(position_market_value: float, fund_weight_pct: float) -> float:
    """Liquidity proxy when no trade tape is available (free-data mode).

    Uses ETF position size and fund weight as stand-ins for depth: index funds
    hold more of (and rebalance more often in) the liquid, large benchmark
    issues. Coarse but directionally consistent with TRACE-based scores.
    """
    size = min(max(position_market_value, 0.0) / 4_000_000.0, 1.0)
    weight = min(max(fund_weight_pct, 0.0) / 0.20, 1.0)
    return round((0.20 + 0.45 * size + 0.35 * weight) * 100.0, 1)


def liquidity_score(
    trade_frequency_weight: float = 0.35,
    size_weight: float = 0.20,
    bid_ask_weight: float = 0.25,
    recency_weight: float = 0.20,
    *,
    trades_per_day: float,
    median_trade_size: float,
    bid_ask_proxy_bps: float | None,
    days_since_last_trade: int,
    distinct_trade_days: int,
    window_days: int,
) -> float:
    """Composite 0-100 liquidity score.

    Components (each normalized to [0, 1]):
      frequency — trades/day, saturating at 10/day
      size      — median trade size, saturating at $1mm
      bid/ask   — tighter proxy spread is better, 100bps -> 0
      recency   — traded today = 1, decays with staleness and sparse trade days
    """
    freq = min(trades_per_day / 10.0, 1.0)
    size = min(median_trade_size / 1_000_000.0, 1.0)
    if bid_ask_proxy_bps is None:
        ba = 0.3  # unknown two-sided market: below-average credit
    else:
        ba = max(0.0, 1.0 - bid_ask_proxy_bps / 100.0)
    coverage = distinct_trade_days / window_days
    recency = max(0.0, 1.0 - days_since_last_trade / 10.0) * (0.5 + 0.5 * min(coverage * 2, 1.0))

    raw = (
        trade_frequency_weight * freq
        + size_weight * size
        + bid_ask_weight * ba
        + recency_weight * recency
    )
    return round(raw * 100.0, 1)
