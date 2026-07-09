import { motion } from 'framer-motion'
import { Link, useParams } from 'react-router-dom'
import { CashflowChart } from '../charts/CashflowChart'
import { CurveChart } from '../charts/CurveChart'
import { DecompositionChart } from '../charts/DecompositionChart'
import { HistoryChart } from '../charts/HistoryChart'
import { CHART } from '../charts/chartTheme'
import { RvBadge } from '../components/RvBadge'
import { StatCard } from '../components/StatCard'
import { useBondDetail, useCurve } from '../hooks/useApi'
import { bps, money, num, pct, px, shortDate, signColor, yearsToMaturity } from '../utils/format'

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-terminal-hairline py-2 last:border-0">
      <span className="text-xs text-terminal-dim">{k}</span>
      <span className="num text-[13px] text-terminal-text">{v}</span>
    </div>
  )
}

function Section({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex items-baseline gap-3 pt-3">
      <h2 className="display text-sm font-semibold tracking-wide text-terminal-text uppercase">{title}</h2>
      {hint && <span className="text-xs text-terminal-faint">{hint}</span>}
      <div className="h-px flex-1 self-center bg-terminal-hairline" />
    </div>
  )
}

export function BondDetailPage() {
  const { cusip } = useParams<{ cusip: string }>()
  const { data, isLoading, error } = useBondDetail(cusip)
  const { data: curve } = useCurve()

  if (isLoading)
    return <div className="p-8 text-terminal-faint">Loading bond analytics…</div>
  if (error || !data)
    return (
      <div className="p-8">
        <div className="text-rich">Bond {cusip} not found.</div>
        <Link to="/" className="text-terminal-accent hover:underline">
          ← Back to monitor
        </Link>
      </div>
    )

  const { bond: b, merton: m, issuer_detail: iss, trade_stats: ts, decomposition } = data

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className="mx-auto max-w-[1700px] space-y-3 p-5"
    >
      {/* Header */}
      <div className="panel flex flex-wrap items-center gap-x-8 gap-y-3 px-6 py-5">
        <div>
          <div className="flex items-center gap-3">
            <span className="display text-2xl font-bold text-terminal-text">{b.issuer}</span>
            <span className="num text-terminal-accent">{b.ticker}</span>
            <RvBadge label={b.rv_label} />
            {b.is_stale && (
              <span className="rounded-xs border border-terminal-accent/40 bg-terminal-accent/10 px-1.5 py-px text-[10px] font-semibold text-terminal-accent uppercase">
                Stale
              </span>
            )}
          </div>
          <div className="num mt-1.5 text-xs text-terminal-dim">
            {b.cusip} · {pct(b.coupon, 3)} due {shortDate(b.maturity_date)} · {data.seniority} ·{' '}
            {b.rating} · {money(b.amount_outstanding)} face
            {data.issue_date < b.maturity_date && <> · issued {shortDate(data.issue_date)}</>}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-8">
          <div className="text-right">
            <div className="text-[10px] tracking-[0.16em] text-terminal-faint uppercase">Price</div>
            <div className="num mt-1 text-2xl text-terminal-text">{px(b.price)}</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] tracking-[0.16em] text-terminal-faint uppercase">Yield</div>
            <div className="num mt-1 text-2xl text-terminal-text">{pct(b.ytm)}</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] tracking-[0.16em] text-terminal-faint uppercase">Z-Spread</div>
            <div className="num mt-1 text-2xl text-terminal-accent">{bps(b.z_spread)}bp</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] tracking-[0.16em] text-terminal-faint uppercase">Mispricing</div>
            <div className={`num mt-1 text-2xl ${signColor(b.residual)}`}>
              {b.residual > 0 ? '+' : ''}
              {bps(b.residual)}bp
            </div>
          </div>
        </div>
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <StatCard label="RV Z-Score" value={num(b.rv_score, 2)} accent={b.rv_label === 'cheap' ? 'cheap' : b.rv_label === 'rich' ? 'rich' : 'none'} sub={`${num(b.rv_percentile, 0)}th pctile`} />
        <StatCard label="Merton PD" value={pct(b.merton_pd, 2)} sub={`${m.maturity.toFixed(1)}y horizon`} />
        <StatCard label="Mkt-Implied PD" value={pct(b.market_implied_pd, 2)} sub={`recovery ${pct(data.recovery_rate, 0)}`} />
        <StatCard label="Dist. to Default" value={num(m.distance_to_default, 2)} sub={m.converged ? `solved in ${m.iterations} iter` : 'not converged'} />
        <StatCard label="Duration" value={num(b.duration, 2)} sub="modified" />
        <StatCard label="Convexity" value={num(b.convexity, 1)} />
        <StatCard label="Liquidity" value={num(b.liquidity_score, 0)} sub={`${ts.trades_per_day.toFixed(1)} trades/day`} />
        <StatCard label="Fair Spread" value={`${bps(b.fair_spread)}bp`} sub={`obs ${bps(b.observed_spread)}bp`} />
      </div>

      <Section title="Market history" hint="how the bond has traded vs the model" />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <HistoryChart
          title="Spread History (bps)"
          data={data.history}
          unit="bp"
          digits={0}
          series={[
            { key: 'z_spread', label: 'Z-spread', color: CHART.accent, transform: (v) => v * 10_000 },
            { key: 'fair_spread', label: 'Fair', color: CHART.blue, transform: (v) => v * 10_000 },
            { key: 'g_spread', label: 'G-spread', color: CHART.purple, transform: (v) => v * 10_000 },
          ]}
        />
        <HistoryChart
          title="Price History"
          data={data.history}
          digits={2}
          series={[{ key: 'price', label: 'Price', color: CHART.cheap }]}
        />
        <HistoryChart
          title="Yield History (%)"
          data={data.history}
          unit="%"
          digits={2}
          series={[{ key: 'ytm', label: 'YTM', color: CHART.accent, transform: (v) => v * 100 }]}
        />
        {curve && (
          <CurveChart
            curve={curve}
            bondPoint={{ maturity: yearsToMaturity(b.maturity_date), ytm: b.ytm, label: b.ticker }}
          />
        )}
      </div>

      <Section title="Credit model" hint="Merton structural view of default risk" />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <HistoryChart
          title="Default Probability (%)"
          data={data.history}
          unit="%"
          digits={2}
          series={[
            { key: 'merton_pd', label: 'Merton PD', color: CHART.rich, transform: (v) => v * 100 },
            { key: 'market_implied_pd', label: 'Mkt-implied', color: CHART.blue, transform: (v) => v * 100 },
          ]}
        />
        <HistoryChart
          title="Distance to Default"
          data={data.history}
          digits={2}
          series={[{ key: 'distance_to_default', label: 'DD', color: CHART.cheap }]}
        />
        <HistoryChart
          title="RV Score History (z)"
          data={data.history}
          digits={2}
          series={[{ key: 'rv_score', label: 'RV z-score', color: CHART.accent }]}
        />
        <HistoryChart
          title="Liquidity Score History"
          data={data.history}
          digits={0}
          series={[{ key: 'liquidity_score', label: 'Liquidity', color: CHART.blue }]}
        />
      </div>

      <Section title="Spread anatomy & cash flows" hint="what the spread pays you for" />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <DecompositionChart decomposition={decomposition} />
        <CashflowChart cashflows={data.cashflows} />
      </div>

      <Section title="Company & market microstructure" />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="panel px-5 pb-3">
          <div className="panel-title -mx-5 mb-2">Merton Structural Model</div>
          <KV k="Firm asset value" v={money(m.asset_value)} />
          <KV k="Asset volatility" v={pct(m.asset_volatility)} />
          <KV k="Equity value" v={money(m.equity_value)} />
          <KV k="Equity volatility" v={pct(m.equity_volatility)} />
          <KV k="Default barrier (debt)" v={money(m.debt_face)} />
          <KV k="Risk-free rate" v={pct(m.risk_free_rate)} />
          <KV k="Distance to default" v={num(m.distance_to_default, 3)} />
          <KV k="Risk-neutral PD" v={pct(m.default_probability, 3)} />
          <KV k="Recovery assumption" v={pct(data.recovery_rate, 0)} />
        </div>
        <div className="panel px-5 pb-3">
          <div className="panel-title -mx-5 mb-2">Capital Structure — {iss.ticker}</div>
          <KV k="Market cap" v={money(iss.market_cap)} />
          <KV k="Enterprise value" v={money(iss.enterprise_value)} />
          <KV k="Total debt" v={money(iss.total_debt)} />
          <KV k="Short-term debt" v={money(iss.short_term_debt)} />
          <KV k="Long-term debt" v={money(iss.long_term_debt)} />
          <KV k="Cash & equivalents" v={money(iss.cash_and_equivalents)} />
          <KV k="Debt / EBITDA" v={num(iss.total_debt / iss.ebitda, 1) + 'x'} />
          <KV k="EBITDA / Interest" v={num(iss.ebitda / iss.interest_expense, 1) + 'x'} />
          <KV k="Beta" v={num(iss.beta, 2)} />
        </div>
        <div className="panel px-5 pb-3">
          <div className="panel-title -mx-5 mb-2">TRACE Liquidity (30d)</div>
          <KV k="Trades" v={ts.trade_count} />
          <KV k="Trades / day" v={num(ts.trades_per_day, 1)} />
          <KV k="VWAP" v={ts.vwap ? px(ts.vwap) : '—'} />
          <KV k="Median trade size" v={ts.median_trade_size ? money(ts.median_trade_size) : '—'} />
          <KV k="Total volume" v={money(ts.total_volume)} />
          <KV k="Bid/ask proxy" v={ts.bid_ask_proxy_bps ? `${num(ts.bid_ask_proxy_bps, 0)}bp` : '—'} />
          <KV k="Daily dispersion" v={ts.avg_daily_spread_bps ? `${num(ts.avg_daily_spread_bps, 0)}bp` : '—'} />
          <KV k="Last trade" v={ts.days_since_last_trade === 0 ? 'today' : `${ts.days_since_last_trade}d ago`} />
          <KV k="Pricing status" v={ts.is_stale ? <span className="text-rich">STALE</span> : <span className="text-cheap">FRESH</span>} />
        </div>
      </div>

      {/* Financials */}
      <div className="panel px-5 pb-3">
        <div className="panel-title -mx-5 mb-2">
          Issuer Financials — {iss.name} · {iss.sector} / {iss.industry} · {iss.rating}
        </div>
        <div className="grid grid-cols-2 gap-x-10 md:grid-cols-4">
          <KV k="Revenue (LTM)" v={money(iss.revenue)} />
          <KV k="EBITDA" v={money(iss.ebitda)} />
          <KV k="Net income" v={money(iss.net_income)} />
          <KV k="Free cash flow" v={money(iss.free_cash_flow)} />
          <KV k="Interest expense" v={money(iss.interest_expense)} />
          <KV k="Total assets" v={money(iss.total_assets)} />
          <KV k="Total equity" v={money(iss.total_equity)} />
          <KV k="Shares outstanding" v={money(iss.shares_outstanding).replace('$', '')} />
        </div>
      </div>

      <Link to="/" className="inline-block pb-4 text-xs text-terminal-accent hover:underline">
        ← Back to monitor
      </Link>
    </motion.div>
  )
}
