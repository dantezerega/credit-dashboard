"""Load REAL market data from free sources, generate DEMO stand-ins for
licensed data, and run the full analytics pipeline.

REAL (free, no API keys):
  - Treasury par yields:  home.treasury.gov daily CSV (full-year history)
  - Bond universe/prices: SPDR ETF daily holdings (SPBO investment grade,
                          SPHY high yield) — real CUSIPs, coupons, maturities,
                          prices derived from market value / par
  - Equity + financials:  Yahoo Finance via yfinance (market cap, realized vol,
                          beta, sector, debt, income statement, price history)
  - Merton PD history:    real equity path x real treasury curves, per day
  - Credit ratings:       market-implied from the bond's real observed spread

DEMO (the underlying feeds are licensed — simulated around the real data and
clearly labeled; the pipeline that consumes them is the real one):
  - TRACE trade tape: synthetic prints generated around each bond's real price,
    with intensity/size driven by its real ETF position size. The liquidity
    score, VWAP, bid/ask proxy, and staleness all come from the REAL TRACE
    processing module run over this demo tape.
  - Bond spread/price history: licensed (no free historical bond prices). Each
    bond gets a mean-reverting demo spread path that ends EXACTLY at today's
    real observed spread, discounted on each day's REAL treasury curve.
    Today's snapshot is fully real; the past is demo. Running daily with
    --update replaces demo days with real accumulated history over time.

Usage:
  python -m app.load_real                        # full refresh (drops tables)
  python -m app.load_real --update               # keep accumulated real history
  python -m app.load_real --history-days 120     # length of demo backfill
  python -m app.load_real --max-issuers 40       # smaller universe (faster)
"""

import argparse
import logging
import random
import time
from collections import defaultdict
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.calculations import bond as bondcalc
from app.calculations.merton import MertonResult, solve_merton
from app.calculations.relative_value import fair_spread, rating_from_spread, score_universe
from app.calculations.trace import compute_trace_metrics, liquidity_score_proxy
from app.calculations.treasury import STANDARD_TENOR_LABELS, STANDARD_TENORS, ZeroCurve, bootstrap_zero_curve
from app.database import Base, SessionLocal, engine
from app.dataloaders.equity_source import EquityData, fetch_equity_data, resolve_tickers
from app.dataloaders.etf_source import EtfHolding, fetch_bond_universe
from app.dataloaders.treasury_source import fetch_treasury_history
from app.models import Bond, BondMetricsDaily, EquityPriceDaily, Issuer, Trade, TreasuryYield

logger = logging.getLogger(__name__)

ALPHA_MEAN_REVERSION = 0.05
ALPHA_DAILY_VOL = 0.00012


def load_treasuries(db: Session, years: list[int]) -> dict[date, ZeroCurve]:
    history = fetch_treasury_history(years)
    if not history:
        raise RuntimeError("No treasury data returned from treasury.gov")
    db.execute(delete(TreasuryYield))
    curves: dict[date, ZeroCurve] = {}
    rows = []
    for d, par in history.items():
        curve = bootstrap_zero_curve(par)
        curves[d] = curve
        for tenor, label in zip(STANDARD_TENORS, STANDARD_TENOR_LABELS):
            if tenor in par:
                rows.append(
                    TreasuryYield(
                        as_of_date=d, tenor=tenor, tenor_label=label,
                        par_yield=par[tenor], zero_rate=curve.zero_rate(tenor),
                    )
                )
    db.add_all(rows)
    db.commit()
    logger.info("Stored %d treasury curve dates (REAL)", len(curves))
    return curves


def select_universe(
    holdings: list[EtfHolding], max_issuers: int, max_bonds_per_issuer: int
) -> dict[str, list[EtfHolding]]:
    """Group bonds by issuer name; keep the largest issuers by total position
    market value (bigger positions = better prices and liquidity signals)."""
    by_issuer: dict[str, list[EtfHolding]] = defaultdict(list)
    for h in holdings:
        by_issuer[h.issuer_name].append(h)
    ranked = sorted(by_issuer.items(), key=lambda kv: -sum(h.market_value for h in kv[1]))
    out: dict[str, list[EtfHolding]] = {}
    for name, bonds in ranked[: max_issuers * 2]:  # oversample: some won't map to equities
        bonds.sort(key=lambda h: -h.market_value)
        out[name] = bonds[:max_bonds_per_issuer]
    return out


def load_issuers_and_bonds(
    db: Session,
    universe: dict[str, list[EtfHolding]],
    max_issuers: int,
) -> tuple[dict[int, EquityData], list[Bond]]:
    """Resolve tickers, pull equity data, persist issuers/bonds/equity history."""
    tickers = resolve_tickers(list(universe.keys()))
    logger.info("Resolved %d/%d issuer names to tickers", len(tickers), len(universe))

    equity_by_issuer_id: dict[int, EquityData] = {}
    bonds: list[Bond] = []
    seen_tickers: set[str] = set()
    kept = 0

    for issuer_name, holdings in universe.items():
        if kept >= max_issuers:
            break
        ticker = tickers.get(issuer_name)
        if not ticker or ticker in seen_tickers:
            continue
        eq = fetch_equity_data(ticker)
        time.sleep(0.4)  # be polite to Yahoo
        if eq is None:
            logger.info("skip %s (%s): no usable equity data", issuer_name, ticker)
            continue
        seen_tickers.add(ticker)
        kept += 1

        # Upsert by ticker so daily --update runs preserve issuer ids (and the
        # bond metric history hanging off their bonds).
        issuer = db.scalar(select(Issuer).where(Issuer.ticker == eq.ticker)) or Issuer(ticker=eq.ticker)
        issuer.name = eq.name
        issuer.sector = eq.sector
        issuer.industry = eq.industry
        issuer.rating = "NR"  # replaced by market-implied rating after pricing
        issuer.market_cap = eq.market_cap
        issuer.equity_volatility = eq.equity_volatility
        issuer.beta = eq.beta
        issuer.shares_outstanding = eq.shares_outstanding
        issuer.total_debt = eq.total_debt
        issuer.short_term_debt = eq.short_term_debt
        issuer.long_term_debt = eq.long_term_debt
        issuer.cash_and_equivalents = eq.cash
        issuer.enterprise_value = eq.market_cap + eq.total_debt - eq.cash
        issuer.revenue = eq.revenue
        issuer.ebitda = eq.ebitda
        issuer.net_income = eq.net_income
        issuer.free_cash_flow = eq.free_cash_flow
        issuer.interest_expense = eq.interest_expense
        issuer.total_assets = eq.total_assets
        issuer.total_equity = eq.total_equity
        db.add(issuer)
        db.flush()
        equity_by_issuer_id[issuer.id] = eq

        db.execute(delete(EquityPriceDaily).where(EquityPriceDaily.issuer_id == issuer.id))
        db.add_all(
            EquityPriceDaily(issuer_id=issuer.id, as_of_date=d, close=close, volume=vol)
            for d, close, vol in eq.price_history
        )
        for h in holdings:
            bond = db.get(Bond, h.cusip) or Bond(cusip=h.cusip)
            bond.issuer_id = issuer.id
            bond.description = h.description
            bond.coupon = h.coupon
            bond.issue_date = h.maturity  # true issue date not in holdings file
            bond.maturity_date = h.maturity
            bond.amount_outstanding = h.par_value
            bond.seniority = h.seniority
            bond.rating = "NR"
            bond.recovery_rate = 0.40
            db.add(bond)
            bonds.append(bond)
        logger.info("loaded %-32s %-6s %d bonds", eq.name[:32], ticker, len(holdings))

    db.commit()
    return equity_by_issuer_id, bonds


def _merton_for(eq: EquityData, mcap: float, rf: float, maturity: float) -> MertonResult:
    """Merton solve with the KMV default barrier (ST debt + half of LT debt)."""
    barrier = (
        eq.short_term_debt + 0.5 * eq.long_term_debt
        if eq.short_term_debt > 0
        else eq.total_debt * 0.6
    )
    return solve_merton(
        equity_value=mcap, equity_volatility=eq.equity_volatility,
        debt_face=barrier, risk_free_rate=rf, maturity=maturity,
    )


def _mcap_path(eq: EquityData, days: list[date]) -> dict[date, float]:
    """REAL market-cap path: today's market cap scaled by the real equity price
    path. Missing dates (holiday mismatches) carry the prior close forward."""
    closes = dict((d, c) for d, c, _ in eq.price_history)
    latest_close = eq.price_history[-1][1]
    path: dict[date, float] = {}
    last = latest_close
    for d in sorted(days):
        last = closes.get(d, last)
        path[d] = eq.market_cap * last / latest_close
    return path


def _demo_alpha_path(rng: random.Random, final_alpha: float, n: int) -> list[float]:
    """DEMO idiosyncratic mispricing path: mean-reverting walk simulated
    backwards from today's real residual, so the path ends exactly on it."""
    path = [final_alpha]
    for _ in range(n - 1):
        path.append(path[-1] * (1 - ALPHA_MEAN_REVERSION) + rng.gauss(0, ALPHA_DAILY_VOL))
    return path[::-1]


def _demo_trades(
    rng: random.Random, cusip: str, d: date, price: float, liq_driver: float
) -> list[Trade]:
    """DEMO TRACE prints for one bond-day around a (real) price level.
    Frequency and size scale with the bond's real ETF position size."""
    trades: list[Trade] = []
    if rng.random() >= 0.25 + 0.72 * liq_driver:
        return trades
    n = max(1, round(rng.expovariate(1 / (1 + 9 * liq_driver))))
    half_spread = (1 - liq_driver) * 0.35 + 0.03
    for _ in range(min(n, 25)):
        side = rng.choice(["B", "S", "S", "B", "D"])
        side_adj = {"B": -half_spread, "S": half_spread, "D": 0.0}[side]
        trades.append(
            Trade(
                cusip=cusip, trade_date=d,
                price=round(price + side_adj + rng.gauss(0, 0.08), 3),
                size=round(rng.lognormvariate(12.2 + 1.8 * liq_driver, 1.0), -3),
                side=side, yield_at_trade=None,
            )
        )
    return trades


def build_history(
    db: Session,
    bonds: list[Bond],
    holdings_by_cusip: dict[str, EtfHolding],
    equity_by_issuer_id: dict[int, EquityData],
    curves: dict[date, ZeroCurve],
    as_of: date,
    history_days: int,
) -> None:
    """Compute metrics for `history_days` business days ending at `as_of`.

    Per day: REAL treasury curve, REAL equity-derived Merton, REAL TRACE
    processing over a DEMO tape, DEMO spread path anchored to today's REAL
    observed spread. Days already present in BondMetricsDaily (accumulated
    real history from prior --update runs) are left untouched.
    """
    curve_dates = sorted(d for d in curves if d <= as_of)[-history_days:]
    if not curve_dates or curve_dates[-1] != as_of:
        curve_dates = [d for d in curve_dates if d < as_of] + [as_of]
    existing = {
        (c, d)
        for c, d in db.execute(
            select(BondMetricsDaily.cusip, BondMetricsDaily.as_of_date).where(
                BondMetricsDaily.as_of_date != as_of
            )
        )
    }
    db.execute(delete(BondMetricsDaily).where(BondMetricsDaily.as_of_date == as_of))
    db.execute(delete(Trade))

    issuers = {i.id: i for i in db.scalars(select(Issuer)).all()}
    n_days = len(curve_dates)

    # Per-bond precomputation over REAL current data.
    state: dict[str, dict] = {}
    for b in bonds:
        h = holdings_by_cusip[b.cusip]
        eq = equity_by_issuer_id[b.issuer_id]
        maturity_now = max((b.maturity_date - as_of).days / 365.25, 0.1)
        cashflows_now = bondcalc.build_cashflows(b.coupon, maturity_now)
        curve_now = curves[curve_dates[-1]] if curve_dates[-1] in curves else curves[max(curves)]
        try:
            z_real = bondcalc.z_spread(cashflows_now, h.price, curve_now)
        except ValueError:
            logger.warning("pricing failed for %s @ %.2f — skipped", b.cusip, h.price)
            continue
        rating = rating_from_spread(z_real)
        b.rating = rating
        issuer = issuers[b.issuer_id]
        if issuer.rating == "NR":
            issuer.rating = rating

        rng = random.Random(f"demo:{b.cusip}")
        liq_driver = liquidity_score_proxy(h.market_value, h.weight_pct) / 100.0
        state[b.cusip] = {
            "bond": b, "holding": h, "eq": eq, "rng": rng,
            "liq_driver": liq_driver, "z_real": z_real,
            "mcap_path": _mcap_path(eq, curve_dates),
            "tape": [],  # accumulated demo trades, chronological
            "fair_by_day": {}, "merton_by_day": {}, "trace_by_day": {}, "extra_by_day": {},
        }

    # Pass 1 (chronological): demo tape -> REAL trace metrics -> fair spread.
    for d in curve_dates:
        curve = curves.get(d) or curves[max(c for c in curves if c <= d)]
        for s in state.values():
            b, h, eq = s["bond"], s["holding"], s["eq"]
            maturity = max((b.maturity_date - d).days / 365.25, 0.1)
            cashflows = bondcalc.build_cashflows(b.coupon, maturity)
            # tape generated around the real-spread price on the day's real curve
            approx_price = bondcalc.price_from_zero_curve(cashflows, curve, s["z_real"])
            day_trades = _demo_trades(s["rng"], b.cusip, d, approx_price, s["liq_driver"])
            s["tape"].extend(day_trades)

            tm = compute_trace_metrics(s["tape"], d)
            merton = _merton_for(eq, s["mcap_path"][d], curve.zero_rate(maturity), maturity)
            fs = fair_spread(
                merton.default_probability, maturity, tm.liquidity_score,
                issuers[b.issuer_id].sector, b.rating, b.recovery_rate,
            )
            s["trace_by_day"][d] = tm
            s["merton_by_day"][d] = merton
            s["fair_by_day"][d] = fs

    db.add_all(t for s in state.values() for t in s["tape"])

    # Pass 2: demo alpha paths anchored at today's real residual, then per-day
    # pricing and cross-sectional scoring.
    metrics: list[BondMetricsDaily] = []
    for s in state.values():
        final_alpha = s["z_real"] - s["fair_by_day"][curve_dates[-1]].fair_spread
        s["alpha"] = dict(zip(curve_dates, _demo_alpha_path(s["rng"], final_alpha, n_days)))

    for i, d in enumerate(curve_dates):
        curve = curves.get(d) or curves[max(c for c in curves if c <= d)]
        is_today = i == n_days - 1
        residuals: dict[str, float] = {}
        records: dict[str, dict] = {}
        for cusip, s in state.items():
            if (cusip, d) in existing:
                continue  # keep previously accumulated real day
            b, h = s["bond"], s["holding"]
            maturity = max((b.maturity_date - d).days / 365.25, 0.1)
            cashflows = bondcalc.build_cashflows(b.coupon, maturity)
            fs = s["fair_by_day"][d]
            observed = s["z_real"] if is_today else max(fs.fair_spread + s["alpha"][d], 0.0002)
            price = h.price if is_today else bondcalc.price_from_zero_curve(cashflows, curve, observed)
            try:
                ytm = bondcalc.yield_from_price(cashflows, price)
            except ValueError:
                continue
            residuals[cusip] = observed - fs.fair_spread
            records[cusip] = {
                "price": price, "ytm": ytm, "observed": observed,
                "g": bondcalc.g_spread(ytm, maturity, curve),
                "oas": bondcalc.oas(cashflows, price, curve),
                "dur": bondcalc.modified_duration(cashflows, ytm),
                "cx": bondcalc.convexity(cashflows, ytm),
                "mkt_pd": bondcalc.market_implied_pd(observed, maturity, b.recovery_rate),
                "merton": s["merton_by_day"][d], "fs": fs, "tm": s["trace_by_day"][d],
            }

        rv = score_universe(residuals)
        for cusip, rec in records.items():
            r = rv[cusip]
            m = rec["merton"]
            fs = rec["fs"]
            tm = rec["tm"]
            metrics.append(
                BondMetricsDaily(
                    cusip=cusip, as_of_date=d,
                    price=rec["price"], ytm=rec["ytm"], g_spread=rec["g"],
                    z_spread=rec["observed"], oas=rec["oas"],
                    duration=rec["dur"], convexity=rec["cx"],
                    merton_pd=m.default_probability, market_implied_pd=rec["mkt_pd"],
                    distance_to_default=m.distance_to_default,
                    asset_value=m.asset_value, asset_volatility=m.asset_volatility,
                    fair_spread=fs.fair_spread, fair_spread_default=fs.default_component,
                    fair_spread_liquidity=fs.liquidity_premium, fair_spread_sector=fs.sector_premium,
                    fair_spread_rating=fs.rating_premium,
                    observed_spread=rec["observed"], residual=r.residual,
                    rv_score=r.z_score, rv_percentile=r.percentile, rv_label=r.label,
                    liquidity_score=tm.liquidity_score, vwap=tm.vwap,
                    trades_per_day=tm.trades_per_day, median_trade_size=tm.median_trade_size,
                    bid_ask_proxy_bps=tm.bid_ask_proxy_bps, is_stale=tm.is_stale,
                )
            )

    db.add_all(metrics)
    db.commit()
    labels = defaultdict(int)
    today_rows = [m for m in metrics if m.as_of_date == curve_dates[-1]]
    for m in today_rows:
        labels[m.rv_label] += 1
    logger.info(
        "Stored %d bond-day metrics across %d days (today REAL: %d bonds, %s)",
        len(metrics), n_days, len(today_rows), dict(labels),
    )


def run(
    max_issuers: int = 60,
    max_bonds_per_issuer: int = 5,
    history_days: int = 90,
    update: bool = False,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if not update:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        today = date.today()
        curves = load_treasuries(db, [today.year - 1, today.year])

        as_of, holdings = fetch_bond_universe()
        universe = select_universe(holdings, max_issuers, max_bonds_per_issuer)
        logger.info("Universe: %d candidate issuers, %d holdings usable", len(universe), len(holdings))

        equity_by_issuer_id, bonds = load_issuers_and_bonds(db, universe, max_issuers)
        logger.info("Persisted %d issuers, %d bonds (REAL)", len(equity_by_issuer_id), len(bonds))

        holdings_by_cusip = {h.cusip: h for h in holdings}
        build_history(db, bonds, holdings_by_cusip, equity_by_issuer_id, curves, as_of, history_days)
        logger.info("Load complete (as of %s)", as_of)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-issuers", type=int, default=60)
    parser.add_argument("--max-bonds-per-issuer", type=int, default=5)
    parser.add_argument("--history-days", type=int, default=90, help="demo backfill length (business days)")
    parser.add_argument("--update", action="store_true", help="keep accumulated real metric history")
    args = parser.parse_args()
    run(args.max_issuers, args.max_bonds_per_issuer, args.history_days, args.update)
