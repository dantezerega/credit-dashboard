"""Relative value engine.

Fair spread = default-risk spread (from Merton PD + recovery)
            + liquidity premium (from liquidity score)
            + sector premium
            + rating premium

Residual = observed spread - fair spread. Cross-sectional z-scores and
percentiles of the residual drive the cheap/rich classification.
"""

import statistics
from dataclasses import dataclass

from app.calculations.bond import spread_from_pd

# Structural premia in decimal spread terms (100bps = 0.01).
SECTOR_PREMIUM_BPS: dict[str, float] = {
    "Technology": 0.0,
    "Healthcare": 5.0,
    "Consumer Staples": 5.0,
    "Consumer Discretionary": 15.0,
    "Industrials": 10.0,
    "Financials": 20.0,
    "Energy": 30.0,
    "Utilities": 8.0,
    "Communications": 12.0,
    "Materials": 18.0,
    "Real Estate": 25.0,
}

RATING_PREMIUM_BPS: dict[str, float] = {
    "AAA": 0.0, "AA+": 2.0, "AA": 4.0, "AA-": 6.0,
    "A+": 10.0, "A": 14.0, "A-": 18.0,
    "BBB+": 25.0, "BBB": 35.0, "BBB-": 50.0,
    "BB+": 80.0, "BB": 110.0, "BB-": 140.0,
    "B+": 200.0, "B": 260.0, "B-": 330.0,
    "CCC+": 450.0, "CCC": 600.0,
}

DEFAULT_RECOVERY_RATE = 0.40
CHEAP_Z_THRESHOLD = 0.75
RICH_Z_THRESHOLD = -0.75


@dataclass(frozen=True)
class FairSpreadResult:
    fair_spread: float
    default_component: float
    liquidity_premium: float
    sector_premium: float
    rating_premium: float


@dataclass(frozen=True)
class RVResult:
    residual: float
    z_score: float
    percentile: float
    label: str  # "cheap" | "rich" | "fair"


# Model-implied rating: 1y-PD buckets calibrated to long-run agency default
# rates. Used when no free ratings feed is available (real-data loader).
PD_RATING_BUCKETS: list[tuple[float, str]] = [
    (0.0002, "AAA"), (0.0005, "AA"), (0.0010, "A+"), (0.0018, "A"), (0.0030, "A-"),
    (0.0050, "BBB+"), (0.0085, "BBB"), (0.0140, "BBB-"), (0.0250, "BB+"),
    (0.0450, "BB"), (0.0750, "BB-"), (0.1200, "B+"), (0.1800, "B"), (0.2600, "B-"),
]


def rating_from_pd(pd_1y: float) -> str:
    """Map a 1-year default probability to a model-implied rating bucket."""
    for threshold, rating in PD_RATING_BUCKETS:
        if pd_1y <= threshold:
            return rating
    return "CCC"


# Spread-implied rating: typical Z-spread bands by rating (bps). Preferred
# over PD-implied ratings for market data — spreads embed a risk premium that
# makes spread-implied PDs run several times historical default rates, which
# would rate everything junk.
SPREAD_RATING_BANDS_BPS: list[tuple[float, str]] = [
    (50, "AAA"), (70, "AA"), (85, "A+"), (100, "A"), (120, "A-"),
    (145, "BBB+"), (175, "BBB"), (220, "BBB-"), (300, "BB+"), (380, "BB"),
    (470, "BB-"), (600, "B+"), (750, "B"), (900, "B-"),
]


def rating_from_spread(spread: float) -> str:
    """Map an observed credit spread (decimal) to a market-implied rating."""
    spread_bps = spread * 10_000
    for threshold, rating in SPREAD_RATING_BANDS_BPS:
        if spread_bps <= threshold:
            return rating
    return "CCC"


def liquidity_premium(liquidity_score: float) -> float:
    """Map a 0-100 liquidity score to a spread premium: perfectly liquid
    bonds earn ~0, fully illiquid ~60bps."""
    score = min(max(liquidity_score, 0.0), 100.0)
    return (100.0 - score) / 100.0 * 0.0060


def fair_spread(
    merton_pd: float,
    maturity: float,
    liquidity_score: float,
    sector: str,
    rating: str,
    recovery_rate: float = DEFAULT_RECOVERY_RATE,
) -> FairSpreadResult:
    default_component = spread_from_pd(merton_pd, maturity, recovery_rate)
    liq = liquidity_premium(liquidity_score)
    sec = SECTOR_PREMIUM_BPS.get(sector, 15.0) / 10_000.0
    rat = RATING_PREMIUM_BPS.get(rating, 100.0) / 10_000.0
    return FairSpreadResult(
        fair_spread=default_component + liq + sec + rat,
        default_component=default_component,
        liquidity_premium=liq,
        sector_premium=sec,
        rating_premium=rat,
    )


def classify(z_score: float) -> str:
    if z_score >= CHEAP_Z_THRESHOLD:
        return "cheap"
    if z_score <= RICH_Z_THRESHOLD:
        return "rich"
    return "fair"


def score_universe(residuals: dict[str, float]) -> dict[str, RVResult]:
    """Cross-sectional scoring: z-score and percentile of each bond's residual
    against the full universe. Positive residual (observed > fair) = cheap."""
    if not residuals:
        return {}
    values = list(residuals.values())
    mean = statistics.mean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)

    out: dict[str, RVResult] = {}
    for key, resid in residuals.items():
        z = (resid - mean) / stdev if stdev > 1e-12 else 0.0
        rank = _rank(sorted_vals, resid)
        pct = rank / (n - 1) * 100.0 if n > 1 else 50.0
        out[key] = RVResult(residual=resid, z_score=z, percentile=pct, label=classify(z))
    return out


def _rank(sorted_vals: list[float], value: float) -> float:
    """Average rank of value in sorted list (handles ties)."""
    lo = 0
    while lo < len(sorted_vals) and sorted_vals[lo] < value:
        lo += 1
    hi = lo
    while hi < len(sorted_vals) and sorted_vals[hi] <= value:
        hi += 1
    return (lo + max(hi - 1, lo)) / 2.0
