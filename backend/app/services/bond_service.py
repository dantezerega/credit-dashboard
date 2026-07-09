"""Bond queries and detail assembly."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.calculations import bond as bondcalc
from app.calculations.merton import solve_merton
from app.calculations.trace import compute_trace_metrics
from app.models import Bond, BondMetricsDaily, Trade, TreasuryYield
from app.schemas.bond import (
    BondDetail,
    BondRow,
    CashFlowItem,
    HistoryPoint,
    IssuerDetail,
    MertonDetail,
    SpreadDecomposition,
    TradeStats,
)


def latest_metrics_date(db: Session) -> date | None:
    return db.scalar(select(func.max(BondMetricsDaily.as_of_date)))


def _to_row(bond: Bond, m: BondMetricsDaily) -> BondRow:
    return BondRow(
        cusip=bond.cusip,
        issuer=bond.issuer.name,
        ticker=bond.issuer.ticker,
        sector=bond.issuer.sector,
        industry=bond.issuer.industry,
        rating=bond.rating,
        coupon=bond.coupon,
        maturity_date=bond.maturity_date,
        price=m.price,
        ytm=m.ytm,
        duration=m.duration,
        convexity=m.convexity,
        g_spread=m.g_spread,
        z_spread=m.z_spread,
        oas=m.oas,
        liquidity_score=m.liquidity_score,
        merton_pd=m.merton_pd,
        market_implied_pd=m.market_implied_pd,
        fair_spread=m.fair_spread,
        observed_spread=m.observed_spread,
        residual=m.residual,
        rv_score=m.rv_score,
        rv_percentile=m.rv_percentile,
        rv_label=m.rv_label,
        is_stale=m.is_stale,
        amount_outstanding=bond.amount_outstanding,
    )


def get_all_bond_rows(db: Session, as_of: date | None = None) -> list[BondRow]:
    as_of = as_of or latest_metrics_date(db)
    if as_of is None:
        return []
    rows = db.execute(
        select(Bond, BondMetricsDaily)
        .join(BondMetricsDaily, BondMetricsDaily.cusip == Bond.cusip)
        .where(BondMetricsDaily.as_of_date == as_of)
        .options(joinedload(Bond.issuer))
    ).all()
    return [_to_row(b, m) for b, m in rows]


def get_bond_detail(db: Session, cusip: str) -> BondDetail | None:
    bond = db.get(Bond, cusip, options=[joinedload(Bond.issuer)])
    if bond is None:
        return None
    as_of = latest_metrics_date(db)
    latest = db.scalar(
        select(BondMetricsDaily)
        .where(BondMetricsDaily.cusip == cusip, BondMetricsDaily.as_of_date == as_of)
    )
    if latest is None or as_of is None:
        return None

    history = db.scalars(
        select(BondMetricsDaily)
        .where(BondMetricsDaily.cusip == cusip)
        .order_by(BondMetricsDaily.as_of_date)
    ).all()

    issuer = bond.issuer
    maturity_years = max((bond.maturity_date - as_of).days / 365.25, 1 / 365.25)
    rf = _risk_free_at(db, as_of, maturity_years)

    merton = solve_merton(
        equity_value=issuer.market_cap,
        equity_volatility=issuer.equity_volatility,
        debt_face=issuer.short_term_debt + 0.5 * issuer.long_term_debt,
        risk_free_rate=rf,
        maturity=maturity_years,
    )

    cashflows = bondcalc.build_cashflows(bond.coupon, maturity_years)
    cf_items = [
        CashFlowItem(
            date=as_of + timedelta(days=round(cf.time * 365.25)),
            time=cf.time,
            amount=cf.amount,
            kind="coupon+principal" if cf.amount > bond.coupon * 100 / 2 + 1e-9 else "coupon",
        )
        for cf in cashflows
    ]

    trades = db.scalars(select(Trade).where(Trade.cusip == cusip)).all()
    tm = compute_trace_metrics(list(trades), as_of)

    return BondDetail(
        bond=_to_row(bond, latest),
        issue_date=bond.issue_date,
        seniority=bond.seniority,
        recovery_rate=bond.recovery_rate,
        issuer_detail=IssuerDetail.model_validate(issuer),
        merton=MertonDetail(
            asset_value=merton.asset_value,
            asset_volatility=merton.asset_volatility,
            distance_to_default=merton.distance_to_default,
            default_probability=merton.default_probability,
            equity_value=issuer.market_cap,
            equity_volatility=issuer.equity_volatility,
            debt_face=merton.debt_face,
            risk_free_rate=rf,
            maturity=maturity_years,
            converged=merton.converged,
            iterations=merton.iterations,
        ),
        decomposition=SpreadDecomposition(
            observed_spread=latest.observed_spread,
            fair_spread=latest.fair_spread,
            default_component=latest.fair_spread_default,
            liquidity_premium=latest.fair_spread_liquidity,
            sector_premium=latest.fair_spread_sector,
            rating_premium=latest.fair_spread_rating,
            residual=latest.residual,
        ),
        cashflows=cf_items,
        history=[
            HistoryPoint(
                as_of_date=h.as_of_date,
                price=h.price,
                ytm=h.ytm,
                g_spread=h.g_spread,
                z_spread=h.z_spread,
                oas=h.oas,
                merton_pd=h.merton_pd,
                market_implied_pd=h.market_implied_pd,
                distance_to_default=h.distance_to_default,
                fair_spread=h.fair_spread,
                residual=h.residual,
                rv_score=h.rv_score,
                liquidity_score=h.liquidity_score,
            )
            for h in history
        ],
        trade_stats=TradeStats(
            trade_count=tm.trade_count,
            trades_per_day=tm.trades_per_day,
            vwap=tm.vwap,
            median_trade_size=tm.median_trade_size,
            total_volume=tm.total_volume,
            bid_ask_proxy_bps=tm.bid_ask_proxy_bps,
            avg_daily_spread_bps=tm.avg_daily_spread_bps,
            days_since_last_trade=tm.days_since_last_trade,
            is_stale=tm.is_stale,
        ),
    )


def _risk_free_at(db: Session, as_of: date, maturity_years: float) -> float:
    """Interpolated zero rate at the given maturity from stored curve."""
    points = db.execute(
        select(TreasuryYield.tenor, TreasuryYield.zero_rate)
        .where(TreasuryYield.as_of_date == as_of)
        .order_by(TreasuryYield.tenor)
    ).all()
    if not points:
        return 0.04
    from app.calculations.treasury import ZeroCurve

    curve = ZeroCurve(tuple(p[0] for p in points), tuple(p[1] for p in points))
    return curve.zero_rate(maturity_years)
