export type RvLabel = 'cheap' | 'rich' | 'fair'

export interface BondRow {
  cusip: string
  issuer: string
  ticker: string
  sector: string
  industry: string
  rating: string
  coupon: number
  maturity_date: string
  price: number
  ytm: number
  duration: number
  convexity: number
  g_spread: number
  z_spread: number
  oas: number
  liquidity_score: number
  merton_pd: number
  market_implied_pd: number
  fair_spread: number
  observed_spread: number
  residual: number
  rv_score: number
  rv_percentile: number
  rv_label: RvLabel
  is_stale: boolean
  amount_outstanding: number
}

export interface HistoryPoint {
  as_of_date: string
  price: number
  ytm: number
  g_spread: number
  z_spread: number
  oas: number
  merton_pd: number
  market_implied_pd: number
  distance_to_default: number
  fair_spread: number
  residual: number
  rv_score: number
  liquidity_score: number
}

export interface CashFlowItem {
  date: string
  time: number
  amount: number
  kind: string
}

export interface SpreadDecomposition {
  observed_spread: number
  fair_spread: number
  default_component: number
  liquidity_premium: number
  sector_premium: number
  rating_premium: number
  residual: number
}

export interface MertonDetail {
  asset_value: number
  asset_volatility: number
  distance_to_default: number
  default_probability: number
  equity_value: number
  equity_volatility: number
  debt_face: number
  risk_free_rate: number
  maturity: number
  converged: boolean
  iterations: number
}

export interface IssuerDetail {
  name: string
  ticker: string
  sector: string
  industry: string
  rating: string
  market_cap: number
  equity_volatility: number
  beta: number
  shares_outstanding: number
  total_debt: number
  short_term_debt: number
  long_term_debt: number
  cash_and_equivalents: number
  enterprise_value: number
  revenue: number
  ebitda: number
  net_income: number
  free_cash_flow: number
  interest_expense: number
  total_assets: number
  total_equity: number
}

export interface TradeStats {
  trade_count: number
  trades_per_day: number
  vwap: number | null
  median_trade_size: number | null
  total_volume: number
  bid_ask_proxy_bps: number | null
  avg_daily_spread_bps: number | null
  days_since_last_trade: number | null
  is_stale: boolean
}

export interface BondDetail {
  bond: BondRow
  issue_date: string
  seniority: string
  recovery_rate: number
  issuer_detail: IssuerDetail
  merton: MertonDetail
  decomposition: SpreadDecomposition
  cashflows: CashFlowItem[]
  history: HistoryPoint[]
  trade_stats: TradeStats
}

export interface CurvePoint {
  tenor: number
  tenor_label: string
  par_yield: number
  zero_rate: number
}

export interface CurveResponse {
  as_of_date: string
  points: CurvePoint[]
}

export interface DashboardSummary {
  as_of_date: string
  bond_count: number
  cheap_count: number
  rich_count: number
  fair_count: number
  avg_spread_bps: number
  avg_rv_score: number
  stale_count: number
  top_cheap: BondRow[]
  top_rich: BondRow[]
}

export interface SearchResult {
  kind: 'bond' | 'issuer'
  cusip: string | null
  ticker: string
  issuer: string
  description: string
  rv_label: RvLabel | null
}

export interface AlertOut {
  id: number
  cusip: string | null
  ticker: string | null
  alert_type: string
  threshold: number
  active: boolean
  created_at: string
  last_triggered_at: string | null
  last_message: string | null
}

export interface AlertCreate {
  cusip?: string | null
  ticker?: string | null
  alert_type: string
  threshold: number
}

export interface AlertTriggered {
  alert_id: number
  cusip: string | null
  ticker: string | null
  alert_type: string
  message: string
}
