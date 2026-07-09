from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class BondRow(BaseModel):
    """One row of the dashboard table."""

    cusip: str
    issuer: str
    ticker: str
    sector: str
    industry: str
    rating: str
    coupon: float
    maturity_date: date
    price: float
    ytm: float
    duration: float
    convexity: float
    g_spread: float
    z_spread: float
    oas: float
    liquidity_score: float
    merton_pd: float
    market_implied_pd: float
    fair_spread: float
    observed_spread: float
    residual: float
    rv_score: float
    rv_percentile: float
    rv_label: str
    is_stale: bool
    amount_outstanding: float


class HistoryPoint(BaseModel):
    as_of_date: date
    price: float
    ytm: float
    g_spread: float
    z_spread: float
    oas: float
    merton_pd: float
    market_implied_pd: float
    distance_to_default: float
    fair_spread: float
    residual: float
    rv_score: float
    liquidity_score: float


class CashFlowItem(BaseModel):
    date: date
    time: float
    amount: float
    kind: str  # coupon | principal | coupon+principal


class SpreadDecomposition(BaseModel):
    observed_spread: float
    fair_spread: float
    default_component: float
    liquidity_premium: float
    sector_premium: float
    rating_premium: float
    residual: float


class MertonDetail(BaseModel):
    asset_value: float
    asset_volatility: float
    distance_to_default: float
    default_probability: float
    equity_value: float
    equity_volatility: float
    debt_face: float
    risk_free_rate: float
    maturity: float
    converged: bool
    iterations: int


class IssuerDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    ticker: str
    sector: str
    industry: str
    rating: str
    market_cap: float
    equity_volatility: float
    beta: float
    shares_outstanding: float
    total_debt: float
    short_term_debt: float
    long_term_debt: float
    cash_and_equivalents: float
    enterprise_value: float
    revenue: float
    ebitda: float
    net_income: float
    free_cash_flow: float
    interest_expense: float
    total_assets: float
    total_equity: float


class BondDetail(BaseModel):
    bond: BondRow
    issue_date: date
    seniority: str
    recovery_rate: float
    issuer_detail: IssuerDetail
    merton: MertonDetail
    decomposition: SpreadDecomposition
    cashflows: list[CashFlowItem]
    history: list[HistoryPoint]
    trade_stats: "TradeStats"


class TradeStats(BaseModel):
    trade_count: int
    trades_per_day: float
    vwap: float | None
    median_trade_size: float | None
    total_volume: float
    bid_ask_proxy_bps: float | None
    avg_daily_spread_bps: float | None
    days_since_last_trade: int | None
    is_stale: bool


class CurvePoint(BaseModel):
    tenor: float
    tenor_label: str
    par_yield: float
    zero_rate: float


class CurveResponse(BaseModel):
    as_of_date: date
    points: list[CurvePoint]


class DashboardSummary(BaseModel):
    as_of_date: date
    bond_count: int
    cheap_count: int
    rich_count: int
    fair_count: int
    avg_spread_bps: float
    avg_rv_score: float
    stale_count: int
    top_cheap: list[BondRow]
    top_rich: list[BondRow]


class ScreenRequest(BaseModel):
    sectors: list[str] | None = None
    industries: list[str] | None = None
    ratings: list[str] | None = None
    tickers: list[str] | None = None
    min_duration: float | None = None
    max_duration: float | None = None
    min_spread_bps: float | None = None
    max_spread_bps: float | None = None
    min_yield: float | None = None
    max_yield: float | None = None
    min_liquidity: float | None = None
    max_pd: float | None = None
    rv_labels: list[str] | None = None
    min_maturity_years: float | None = None
    max_maturity_years: float | None = None
    sort_by: str = "rv_score"
    sort_dir: str = "desc"
    limit: int = 500


class SearchResult(BaseModel):
    kind: str  # bond | issuer
    cusip: str | None = None
    ticker: str
    issuer: str
    description: str
    rv_label: str | None = None


class AlertCreate(BaseModel):
    cusip: str | None = None
    ticker: str | None = None
    alert_type: str
    threshold: float


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cusip: str | None
    ticker: str | None
    alert_type: str
    threshold: float
    active: bool
    created_at: datetime
    last_triggered_at: datetime | None
    last_message: str | None


class AlertTriggered(BaseModel):
    alert_id: int
    cusip: str | None
    ticker: str | None
    alert_type: str
    message: str


class MertonRequest(BaseModel):
    equity_value: float
    equity_volatility: float
    debt_face: float
    risk_free_rate: float
    maturity: float = 1.0
