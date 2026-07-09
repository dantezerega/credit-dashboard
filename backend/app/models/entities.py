from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Issuer(Base):
    __tablename__ = "issuers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    ticker: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(64), index=True)
    industry: Mapped[str] = mapped_column(String(64))
    rating: Mapped[str] = mapped_column(String(8), index=True)

    # Equity / capital structure snapshot (latest)
    market_cap: Mapped[float] = mapped_column(Float)  # USD
    equity_volatility: Mapped[float] = mapped_column(Float)  # annualized
    beta: Mapped[float] = mapped_column(Float)
    shares_outstanding: Mapped[float] = mapped_column(Float)
    total_debt: Mapped[float] = mapped_column(Float)
    short_term_debt: Mapped[float] = mapped_column(Float)
    long_term_debt: Mapped[float] = mapped_column(Float)
    cash_and_equivalents: Mapped[float] = mapped_column(Float)
    enterprise_value: Mapped[float] = mapped_column(Float)

    # Financial statement summary (LTM)
    revenue: Mapped[float] = mapped_column(Float)
    ebitda: Mapped[float] = mapped_column(Float)
    net_income: Mapped[float] = mapped_column(Float)
    free_cash_flow: Mapped[float] = mapped_column(Float)
    interest_expense: Mapped[float] = mapped_column(Float)
    total_assets: Mapped[float] = mapped_column(Float)
    total_equity: Mapped[float] = mapped_column(Float)

    bonds: Mapped[list["Bond"]] = relationship(back_populates="issuer")
    equity_prices: Mapped[list["EquityPriceDaily"]] = relationship(back_populates="issuer")


class Bond(Base):
    __tablename__ = "bonds"

    cusip: Mapped[str] = mapped_column(String(9), primary_key=True)
    issuer_id: Mapped[int] = mapped_column(ForeignKey("issuers.id"), index=True)
    description: Mapped[str] = mapped_column(String(128))
    coupon: Mapped[float] = mapped_column(Float)  # decimal, 0.045 = 4.5%
    issue_date: Mapped[date] = mapped_column(Date)
    maturity_date: Mapped[date] = mapped_column(Date, index=True)
    amount_outstanding: Mapped[float] = mapped_column(Float)  # USD face
    seniority: Mapped[str] = mapped_column(String(32), default="Senior Unsecured")
    rating: Mapped[str] = mapped_column(String(8), index=True)
    recovery_rate: Mapped[float] = mapped_column(Float, default=0.40)

    issuer: Mapped[Issuer] = relationship(back_populates="bonds")
    metrics: Mapped[list["BondMetricsDaily"]] = relationship(back_populates="bond")
    trades: Mapped[list["Trade"]] = relationship(back_populates="bond")


class BondMetricsDaily(Base):
    """Daily analytics snapshot per bond — output of the full pipeline."""

    __tablename__ = "bond_metrics_daily"
    __table_args__ = (Index("ix_metrics_cusip_date", "cusip", "as_of_date", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cusip: Mapped[str] = mapped_column(ForeignKey("bonds.cusip"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)

    price: Mapped[float] = mapped_column(Float)
    ytm: Mapped[float] = mapped_column(Float)
    g_spread: Mapped[float] = mapped_column(Float)
    z_spread: Mapped[float] = mapped_column(Float)
    oas: Mapped[float] = mapped_column(Float)
    duration: Mapped[float] = mapped_column(Float)
    convexity: Mapped[float] = mapped_column(Float)

    merton_pd: Mapped[float] = mapped_column(Float)
    market_implied_pd: Mapped[float] = mapped_column(Float)
    distance_to_default: Mapped[float] = mapped_column(Float)
    asset_value: Mapped[float] = mapped_column(Float)
    asset_volatility: Mapped[float] = mapped_column(Float)

    fair_spread: Mapped[float] = mapped_column(Float)
    fair_spread_default: Mapped[float] = mapped_column(Float)
    fair_spread_liquidity: Mapped[float] = mapped_column(Float)
    fair_spread_sector: Mapped[float] = mapped_column(Float)
    fair_spread_rating: Mapped[float] = mapped_column(Float)
    observed_spread: Mapped[float] = mapped_column(Float)
    residual: Mapped[float] = mapped_column(Float)
    rv_score: Mapped[float] = mapped_column(Float)  # cross-sectional z-score
    rv_percentile: Mapped[float] = mapped_column(Float)
    rv_label: Mapped[str] = mapped_column(String(8), index=True)  # cheap | rich | fair

    liquidity_score: Mapped[float] = mapped_column(Float)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    trades_per_day: Mapped[float] = mapped_column(Float, default=0.0)
    median_trade_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_ask_proxy_bps: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)

    bond: Mapped[Bond] = relationship(back_populates="metrics")


class Trade(Base):
    """TRACE-style trade print."""

    __tablename__ = "trades"
    __table_args__ = (Index("ix_trades_cusip_date", "cusip", "trade_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cusip: Mapped[str] = mapped_column(ForeignKey("bonds.cusip"))
    trade_date: Mapped[date] = mapped_column(Date)
    price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)  # USD face
    side: Mapped[str] = mapped_column(String(1))  # B = dealer buy, S = dealer sell, D = inter-dealer
    yield_at_trade: Mapped[float | None] = mapped_column(Float, nullable=True)

    bond: Mapped[Bond] = relationship(back_populates="trades")


class TreasuryYield(Base):
    __tablename__ = "treasury_yields"
    __table_args__ = (Index("ix_treasury_date_tenor", "as_of_date", "tenor", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    tenor: Mapped[float] = mapped_column(Float)  # years
    tenor_label: Mapped[str] = mapped_column(String(4))
    par_yield: Mapped[float] = mapped_column(Float)
    zero_rate: Mapped[float] = mapped_column(Float)


class EquityPriceDaily(Base):
    __tablename__ = "equity_prices_daily"
    __table_args__ = (Index("ix_equity_issuer_date", "issuer_id", "as_of_date", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issuer_id: Mapped[int] = mapped_column(ForeignKey("issuers.id"))
    as_of_date: Mapped[date] = mapped_column(Date)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)

    issuer: Mapped[Issuer] = relationship(back_populates="equity_prices")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cusip: Mapped[str | None] = mapped_column(ForeignKey("bonds.cusip"), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(12), nullable=True)  # issuer-level alerts
    alert_type: Mapped[str] = mapped_column(String(32))
    # becomes_cheap | becomes_rich | spread_widens | spread_tightens | pd_spike | liquidity_drop
    threshold: Mapped[float] = mapped_column(Float)  # bps for spread moves, % for PD, points for liquidity
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message: Mapped[str | None] = mapped_column(String(256), nullable=True)
