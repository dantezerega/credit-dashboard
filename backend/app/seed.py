"""Seed the database with a realistic synthetic credit universe.

Generates ~40 issuers, ~150 bonds, 180 calendar days of treasury curves,
equity prices, and TRACE-style trade prints, then runs the full analytics
pipeline (Merton -> fair spread -> residual -> cross-sectional RV scoring)
for every bond, every business day, and stores daily metric snapshots.

Deterministic (seeded RNG) so repeated runs produce the same universe.

Usage:  python -m app.seed
"""

import logging
import math
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.calculations import bond as bondcalc
from app.calculations.merton import solve_merton
from app.calculations.relative_value import fair_spread, score_universe
from app.calculations.trace import compute_trace_metrics
from app.calculations.treasury import STANDARD_TENOR_LABELS, STANDARD_TENORS, bootstrap_zero_curve
from app.database import Base, SessionLocal, engine
from app.models import Alert, Bond, BondMetricsDaily, EquityPriceDaily, Issuer, Trade, TreasuryYield

logger = logging.getLogger(__name__)
rng = random.Random(42)

AS_OF = date(2026, 7, 7)
HISTORY_CALENDAR_DAYS = 180

RATING_LADDER = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B"]

ISSUER_SEEDS: list[tuple[str, str, str, str, str, float]] = [
    # name, ticker, sector, industry, rating, market_cap ($bn)
    ("Apexon Technologies", "APXT", "Technology", "Software", "AA-", 380),
    ("Cirrus Semiconductor", "CRSM", "Technology", "Semiconductors", "A+", 210),
    ("Quantel Systems", "QNTL", "Technology", "IT Hardware", "BBB+", 85),
    ("Nimbus Cloud Corp", "NMBC", "Technology", "Cloud Infrastructure", "BBB", 62),
    ("Veritas Data Group", "VRDG", "Technology", "Data Analytics", "BB+", 18),
    ("Meridian Health", "MRDH", "Healthcare", "Managed Care", "A", 145),
    ("BioCrest Pharma", "BCRP", "Healthcare", "Pharmaceuticals", "A-", 120),
    ("Stellar Medical Devices", "STMD", "Healthcare", "Med Devices", "BBB+", 48),
    ("Genova Therapeutics", "GNVA", "Healthcare", "Biotech", "BB", 12),
    ("Coastal Grocers", "CSTG", "Consumer Staples", "Food Retail", "BBB", 34),
    ("Pinnacle Beverages", "PNBV", "Consumer Staples", "Beverages", "A", 95),
    ("HomeGuard Products", "HGPD", "Consumer Staples", "Household Products", "A-", 55),
    ("Traverse Motors", "TRVM", "Consumer Discretionary", "Autos", "BBB-", 58),
    ("UrbanNest Retail", "UNRT", "Consumer Discretionary", "E-Commerce", "BBB+", 72),
    ("Summit Hospitality", "SMHT", "Consumer Discretionary", "Hotels", "BB+", 15),
    ("Falcon Apparel", "FLCA", "Consumer Discretionary", "Apparel", "BB", 8),
    ("Ironbridge Industries", "IRBG", "Industrials", "Machinery", "BBB+", 44),
    ("AeroDyne Corp", "ARDN", "Industrials", "Aerospace & Defense", "A-", 105),
    ("Continental Freight", "CNFR", "Industrials", "Logistics", "BBB", 38),
    ("Vulcan Construction", "VLCN", "Industrials", "Construction", "BB+", 11),
    ("Atlas National Bank", "ATNB", "Financials", "Banks", "A", 165),
    ("Sterling Trust Group", "STTG", "Financials", "Asset Management", "A-", 78),
    ("Harbor Insurance", "HRBI", "Financials", "Insurance", "A+", 92),
    ("Crestline Capital", "CRLC", "Financials", "Consumer Finance", "BBB", 26),
    ("Petrova Energy", "PTVE", "Energy", "Integrated Oil", "BBB+", 130),
    ("Redrock Exploration", "RDRX", "Energy", "E&P", "BB+", 22),
    ("Gulfstream Midstream", "GFMS", "Energy", "Midstream", "BBB-", 31),
    ("Solaris Renewables", "SLRN", "Energy", "Renewables", "BB", 9),
    ("Granite Power & Light", "GRPL", "Utilities", "Electric Utilities", "A-", 68),
    ("BlueRiver Water Co", "BRWC", "Utilities", "Water Utilities", "A", 24),
    ("Heartland Gas", "HRTG", "Utilities", "Gas Distribution", "BBB+", 19),
    ("Signalwave Communications", "SGWV", "Communications", "Telecom", "BBB", 88),
    ("Orbit Media Group", "OBMG", "Communications", "Media", "BB+", 21),
    ("Streamline Entertainment", "STME", "Communications", "Streaming", "BB", 35),
    ("Ferrocore Metals", "FRCM", "Materials", "Steel", "BB+", 14),
    ("Cascade Chemical", "CSCH", "Materials", "Chemicals", "BBB", 42),
    ("Timberline Paper", "TMBP", "Materials", "Paper & Packaging", "BBB-", 16),
    ("Keystone Properties", "KYPR", "Real Estate", "Office REIT", "BBB-", 13),
    ("Silverpoint Storage", "SLPS", "Real Estate", "Storage REIT", "BBB", 20),
    ("Metroview Residential", "MTVR", "Real Estate", "Residential REIT", "BBB+", 28),
]

RATING_VOL = {  # equity vol anchored to credit quality
    "AAA": 0.16, "AA+": 0.17, "AA": 0.18, "AA-": 0.19, "A+": 0.20, "A": 0.22, "A-": 0.24,
    "BBB+": 0.27, "BBB": 0.30, "BBB-": 0.34, "BB+": 0.38, "BB": 0.43, "BB-": 0.48, "B+": 0.55, "B": 0.62,
}
RATING_LEVERAGE = {  # debt / market cap
    "AAA": 0.10, "AA+": 0.12, "AA": 0.15, "AA-": 0.18, "A+": 0.22, "A": 0.28, "A-": 0.34,
    "BBB+": 0.42, "BBB": 0.52, "BBB-": 0.65, "BB+": 0.85, "BB": 1.05, "BB-": 1.30, "B+": 1.60, "B": 2.00,
}

BASE_PAR_YIELDS = {  # gently upward-sloping starting curve
    1 / 12: 0.0430, 0.25: 0.0435, 0.5: 0.0438, 1: 0.0440, 2: 0.0432, 3: 0.0428,
    5: 0.0430, 7: 0.0438, 10: 0.0448, 20: 0.0472, 30: 0.0480,
}


def business_days(end: date, calendar_days: int) -> list[date]:
    days = []
    d = end - timedelta(days=calendar_days)
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def make_cusip(i: int) -> str:
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return f"{letters[i % 24]}{letters[(i // 24) % 24]}{i % 10}{(i * 7) % 10}{(i * 3) % 10}{letters[(i * 5) % 24]}{i % 10}{(i + 3) % 10}{(i * 9 + 1) % 10}"


def build_issuers(db: Session) -> list[Issuer]:
    issuers = []
    for name, ticker, sector, industry, rating, mcap_bn in ISSUER_SEEDS:
        mcap = mcap_bn * 1e9
        vol = RATING_VOL[rating] * rng.uniform(0.9, 1.1)
        leverage = RATING_LEVERAGE[rating] * rng.uniform(0.85, 1.15)
        debt = mcap * leverage
        st_debt = debt * rng.uniform(0.15, 0.35)
        cash = mcap * rng.uniform(0.04, 0.15)
        shares = mcap / rng.uniform(20, 400)
        revenue = mcap * rng.uniform(0.3, 1.2)
        ebitda_margin = rng.uniform(0.12, 0.38)
        ebitda = revenue * ebitda_margin
        issuer = Issuer(
            name=name, ticker=ticker, sector=sector, industry=industry, rating=rating,
            market_cap=mcap, equity_volatility=vol, beta=rng.uniform(0.7, 1.6),
            shares_outstanding=shares, total_debt=debt, short_term_debt=st_debt,
            long_term_debt=debt - st_debt, cash_and_equivalents=cash,
            enterprise_value=mcap + debt - cash, revenue=revenue, ebitda=ebitda,
            net_income=ebitda * rng.uniform(0.25, 0.55),
            free_cash_flow=ebitda * rng.uniform(0.3, 0.6),
            interest_expense=debt * rng.uniform(0.035, 0.06),
            total_assets=mcap * rng.uniform(0.8, 2.5) + debt,
            total_equity=mcap * rng.uniform(0.4, 0.9),
        )
        issuers.append(issuer)
    db.add_all(issuers)
    db.commit()
    return issuers


def build_bonds(db: Session, issuers: list[Issuer]) -> list[Bond]:
    bonds = []
    idx = 0
    for issuer in issuers:
        n_bonds = rng.choice([2, 3, 4, 4, 5])
        rating_i = RATING_LADDER.index(issuer.rating)
        for _ in range(n_bonds):
            years_out = rng.choice([2, 3, 5, 7, 10, 15, 20, 30]) + rng.uniform(-0.4, 0.4)
            maturity = AS_OF + timedelta(days=round(years_out * 365.25))
            issued = AS_OF - timedelta(days=round(rng.uniform(0.5, 8) * 365.25))
            coupon = round(BASE_PAR_YIELDS[10] + rating_i * 0.0018 + rng.uniform(-0.005, 0.012), 4)
            bond_rating = RATING_LADDER[min(max(rating_i + rng.choice([-1, 0, 0, 0, 1]), 0), len(RATING_LADDER) - 1)]
            bonds.append(
                Bond(
                    cusip=make_cusip(idx),
                    issuer_id=issuer.id,
                    description=f"{issuer.ticker} {coupon * 100:.3f} {maturity.strftime('%m/%d/%y')}",
                    coupon=coupon,
                    issue_date=issued,
                    maturity_date=maturity,
                    amount_outstanding=rng.choice([300, 500, 500, 750, 1000, 1250, 1500]) * 1e6,
                    seniority=rng.choice(["Senior Unsecured"] * 4 + ["Senior Secured", "Subordinated"]),
                    rating=bond_rating,
                    recovery_rate=0.40,
                )
            )
            idx += 1
    db.add_all(bonds)
    db.commit()
    return bonds


def build_treasury_history(db: Session, days: list[date]) -> dict[date, "object"]:
    """Random-walk par curve per day; bootstrap zero curve; store both."""
    curves = {}
    par = dict(BASE_PAR_YIELDS)
    rows = []
    for d in days:
        # small correlated parallel shift + slope noise
        shift = rng.gauss(0, 0.00035)
        slope = rng.gauss(0, 0.00015)
        for t in par:
            par[t] = max(0.005, par[t] + shift + slope * (t - 5) / 25)
        curve = bootstrap_zero_curve(par)
        curves[d] = curve
        for tenor, label in zip(STANDARD_TENORS, STANDARD_TENOR_LABELS):
            rows.append(
                TreasuryYield(
                    as_of_date=d, tenor=tenor, tenor_label=label,
                    par_yield=par[tenor], zero_rate=curve.zero_rate(tenor),
                )
            )
    db.add_all(rows)
    db.commit()
    return curves


def build_equity_history(db: Session, issuers: list[Issuer], days: list[date]) -> dict[int, dict[date, float]]:
    """GBM path per issuer ending at current market cap. Returns market-cap paths."""
    paths: dict[int, dict[date, float]] = {}
    rows = []
    n = len(days)
    for issuer in issuers:
        vol_daily = issuer.equity_volatility / math.sqrt(252)
        # simulate forward then rescale so the final point equals today's mcap
        raw = [1.0]
        for _ in range(n - 1):
            raw.append(raw[-1] * math.exp(rng.gauss(0, vol_daily)))
        scale = 1.0 / raw[-1]
        price0 = issuer.market_cap / issuer.shares_outstanding
        path = {}
        for d, level in zip(days, raw):
            mcap = issuer.market_cap * level * scale
            path[d] = mcap
            rows.append(
                EquityPriceDaily(
                    issuer_id=issuer.id, as_of_date=d,
                    close=price0 * level * scale,
                    volume=issuer.shares_outstanding * rng.uniform(0.002, 0.012),
                )
            )
        paths[issuer.id] = path
    db.add_all(rows)
    db.commit()
    return paths


def build_metrics_and_trades(
    db: Session,
    bonds: list[Bond],
    issuers: list[Issuer],
    curves: dict[date, "object"],
    mcap_paths: dict[int, dict[date, float]],
    days: list[date],
) -> None:
    issuer_by_id = {i.id: i for i in issuers}

    # Persistent bond-level state: idiosyncratic alpha (the mispricing RV should
    # detect, mean-reverting) and a liquidity profile.
    alpha: dict[str, float] = {b.cusip: rng.gauss(0, 0.0018) for b in bonds}
    liq_profile: dict[str, float] = {
        b.cusip: min(1.0, 0.25 + b.amount_outstanding / 1.5e9 + rng.uniform(-0.15, 0.35)) for b in bonds
    }

    trades_by_cusip: dict[str, list[Trade]] = {b.cusip: [] for b in bonds}
    all_trades: list[Trade] = []
    all_metrics: list[BondMetricsDaily] = []

    for day_idx, d in enumerate(days):
        curve = curves[d]
        residuals: dict[str, float] = {}
        day_records: dict[str, dict] = {}

        for b in bonds:
            issuer = issuer_by_id[b.issuer_id]
            maturity_years = max((b.maturity_date - d).days / 365.25, 0.25)
            rf = curve.zero_rate(maturity_years)
            mcap = mcap_paths[issuer.id][d]

            merton = solve_merton(
                equity_value=mcap,
                equity_volatility=issuer.equity_volatility,
                debt_face=issuer.short_term_debt + 0.5 * issuer.long_term_debt,
                risk_free_rate=rf,
                maturity=maturity_years,
            )

            # mean-reverting idiosyncratic alpha + observation noise
            alpha[b.cusip] += -0.05 * alpha[b.cusip] + rng.gauss(0, 0.00012)

            # trades for this day (need liquidity score before fair spread)
            cashflows = bondcalc.build_cashflows(b.coupon, maturity_years)
            liq = liq_profile[b.cusip]

            # provisional fair spread with mid liquidity, refined after trace calc
            fs0 = fair_spread(
                merton.default_probability, maturity_years, liq * 100, issuer.sector, b.rating, b.recovery_rate
            )
            observed = max(fs0.fair_spread + alpha[b.cusip] + rng.gauss(0, 0.0004), 0.0002)
            price = bondcalc.price_from_zero_curve(cashflows, curve, observed)

            n_trades = 0
            if rng.random() < 0.25 + 0.72 * liq:
                n_trades = max(1, round(rng.expovariate(1 / (1 + 9 * liq))))
            half_spread = (1 - liq) * 0.35 + 0.03
            day_trades = []
            for _ in range(min(n_trades, 25)):
                side = rng.choice(["B", "S", "S", "B", "D"])
                side_adj = {"B": -half_spread, "S": half_spread, "D": 0.0}[side]
                day_trades.append(
                    Trade(
                        cusip=b.cusip, trade_date=d,
                        price=round(price + side_adj + rng.gauss(0, 0.08), 3),
                        size=round(rng.lognormvariate(12.2 + 1.8 * liq, 1.0), -3),
                        side=side,
                        yield_at_trade=None,
                    )
                )
            trades_by_cusip[b.cusip].extend(day_trades)
            all_trades.extend(day_trades)

            tm = compute_trace_metrics(trades_by_cusip[b.cusip], d)
            fs = fair_spread(
                merton.default_probability, maturity_years, tm.liquidity_score,
                issuer.sector, b.rating, b.recovery_rate,
            )

            ytm = bondcalc.yield_from_price(cashflows, price)
            residual = observed - fs.fair_spread
            residuals[b.cusip] = residual
            day_records[b.cusip] = {
                "bond": b, "price": price, "ytm": ytm,
                "g_spread": bondcalc.g_spread(ytm, maturity_years, curve),
                "z_spread": observed,
                "oas": bondcalc.oas(cashflows, price, curve),
                "duration": bondcalc.modified_duration(cashflows, ytm),
                "convexity": bondcalc.convexity(cashflows, ytm),
                "merton": merton,
                "market_implied_pd": bondcalc.market_implied_pd(observed, maturity_years, b.recovery_rate),
                "fs": fs, "observed": observed, "tm": tm,
            }

        rv = score_universe(residuals)
        for cusip, rec in day_records.items():
            r = rv[cusip]
            m = rec["merton"]
            fs = rec["fs"]
            tm = rec["tm"]
            all_metrics.append(
                BondMetricsDaily(
                    cusip=cusip, as_of_date=d,
                    price=rec["price"], ytm=rec["ytm"], g_spread=rec["g_spread"],
                    z_spread=rec["z_spread"], oas=rec["oas"],
                    duration=rec["duration"], convexity=rec["convexity"],
                    merton_pd=m.default_probability, market_implied_pd=rec["market_implied_pd"],
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

        if (day_idx + 1) % 20 == 0:
            logger.info("Processed %d/%d days", day_idx + 1, len(days))

    db.add_all(all_trades)
    db.commit()
    db.add_all(all_metrics)
    db.commit()


def seed_demo_alerts(db: Session, bonds: list[Bond]) -> None:
    db.add_all([
        Alert(cusip=bonds[3].cusip, alert_type="becomes_cheap", threshold=0),
        Alert(cusip=bonds[10].cusip, alert_type="spread_widens", threshold=10),
        Alert(ticker="PTVE", alert_type="pd_spike", threshold=0.5),
    ])
    db.commit()


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        days = business_days(AS_OF, HISTORY_CALENDAR_DAYS)
        logger.info("Seeding %d business days ending %s", len(days), AS_OF)
        issuers = build_issuers(db)
        bonds = build_bonds(db, issuers)
        logger.info("Created %d issuers, %d bonds", len(issuers), len(bonds))
        curves = build_treasury_history(db, days)
        logger.info("Treasury curves bootstrapped")
        mcap_paths = build_equity_history(db, issuers, days)
        logger.info("Equity histories generated")
        build_metrics_and_trades(db, bonds, issuers, curves, mcap_paths, days)
        seed_demo_alerts(db, bonds)
        logger.info("Seed complete")
    finally:
        db.close()


if __name__ == "__main__":
    run()
