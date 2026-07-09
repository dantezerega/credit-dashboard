import { motion } from 'framer-motion'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { AlertTriggered } from '../api/types'
import {
  useAlerts,
  useCreateAlert,
  useDeleteAlert,
  useEvaluateAlerts,
} from '../hooks/useApi'
import { shortDate } from '../utils/format'

const ALERT_TYPES = [
  { value: 'becomes_cheap', label: 'Becomes cheap', unit: '' },
  { value: 'becomes_rich', label: 'Becomes rich', unit: '' },
  { value: 'spread_widens', label: 'Spread widens', unit: 'bps' },
  { value: 'spread_tightens', label: 'Spread tightens', unit: 'bps' },
  { value: 'pd_spike', label: 'PD spikes', unit: 'pp' },
  { value: 'liquidity_drop', label: 'Liquidity drops', unit: 'pts' },
]

export function AlertsPage() {
  const { data: alerts } = useAlerts()
  const createAlert = useCreateAlert()
  const deleteAlert = useDeleteAlert()
  const evaluate = useEvaluateAlerts()
  const [triggered, setTriggered] = useState<AlertTriggered[] | null>(null)

  const [target, setTarget] = useState('')
  const [alertType, setAlertType] = useState('becomes_cheap')
  const [threshold, setThreshold] = useState('10')

  const typeInfo = ALERT_TYPES.find((t) => t.value === alertType)
  const needsThreshold = !alertType.startsWith('becomes_')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const t = target.trim().toUpperCase()
    if (!t) return
    const isCusip = t.length === 9
    createAlert.mutate(
      {
        cusip: isCusip ? t : null,
        ticker: isCusip ? null : t,
        alert_type: alertType,
        threshold: needsThreshold ? Number(threshold) : 0,
      },
      { onSuccess: () => setTarget('') },
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <div className="panel p-6">
        <div className="mb-4 text-[11px] font-semibold tracking-[0.14em] text-terminal-dim uppercase">
          Create Alert
        </div>
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] tracking-wider text-terminal-faint uppercase">
              CUSIP or Ticker
            </span>
            <input
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="e.g. PTVE or AA000A031"
              className="num w-44 rounded-md border border-terminal-border bg-terminal-bg px-2 py-1.5 text-sm placeholder-terminal-faint focus:border-terminal-accent focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] tracking-wider text-terminal-faint uppercase">Condition</span>
            <select
              value={alertType}
              onChange={(e) => setAlertType(e.target.value)}
              className="rounded-md border border-terminal-border bg-terminal-bg px-2 py-1.5 text-sm focus:border-terminal-accent focus:outline-none"
            >
              {ALERT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          {needsThreshold && (
            <label className="flex flex-col gap-1">
              <span className="text-[10px] tracking-wider text-terminal-faint uppercase">
                Threshold ({typeInfo?.unit})
              </span>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="num w-24 rounded-md border border-terminal-border bg-terminal-bg px-2 py-1.5 text-sm focus:border-terminal-accent focus:outline-none"
              />
            </label>
          )}
          <button
            type="submit"
            disabled={createAlert.isPending || !target.trim()}
            className="rounded-md border border-terminal-accent bg-terminal-accent/15 px-4 py-1.5 text-[11px] font-semibold tracking-wider text-terminal-accent uppercase transition-colors hover:bg-terminal-accent/25 disabled:opacity-40"
          >
            Add Alert
          </button>
          <button
            type="button"
            onClick={() => evaluate.mutate(undefined, { onSuccess: setTriggered })}
            disabled={evaluate.isPending}
            className="rounded-md border border-terminal-border px-4 py-1.5 text-[11px] font-semibold tracking-wider text-terminal-dim uppercase transition-colors hover:text-terminal-text disabled:opacity-40"
          >
            {evaluate.isPending ? 'Evaluating…' : 'Run Evaluation'}
          </button>
        </form>
        {createAlert.isError && (
          <div className="mt-2 text-[11px] text-rich">{String(createAlert.error)}</div>
        )}
      </div>

      {triggered && (
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="panel p-6">
          <div className="mb-3 text-[11px] font-semibold tracking-[0.14em] text-terminal-dim uppercase">
            Evaluation Result
          </div>
          {triggered.length === 0 ? (
            <div className="text-sm text-terminal-faint">No alerts triggered on latest snapshot.</div>
          ) : (
            <ul className="space-y-1">
              {triggered.map((t, i) => (
                <li key={i} className="num text-sm text-terminal-accent">
                  ▲ {t.message}
                  {t.cusip && (
                    <Link to={`/bond/${t.cusip}`} className="ml-2 text-terminal-dim hover:underline">
                      view →
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
        </motion.div>
      )}

      <div className="panel">
        <div className="panel-title">Active Alerts ({alerts?.length ?? 0})</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-terminal-border text-left text-[10px] tracking-wider text-terminal-faint uppercase">
              <th className="px-4 py-2.5">Target</th>
              <th className="px-4 py-2.5">Condition</th>
              <th className="px-4 py-2.5 text-right">Threshold</th>
              <th className="px-4 py-2.5">Created</th>
              <th className="px-4 py-2.5">Last Triggered</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {(alerts ?? []).map((a) => (
              <tr key={a.id} className="border-b border-terminal-hairline">
                <td className="num px-4 py-2.5 text-terminal-accent">
                  {a.cusip ? (
                    <Link to={`/bond/${a.cusip}`} className="hover:underline">
                      {a.cusip}
                    </Link>
                  ) : (
                    a.ticker
                  )}
                </td>
                <td className="px-4 py-2.5">
                  {ALERT_TYPES.find((t) => t.value === a.alert_type)?.label ?? a.alert_type}
                </td>
                <td className="num px-4 py-2.5 text-right">
                  {a.alert_type.startsWith('becomes_') ? '—' : a.threshold}
                </td>
                <td className="num px-4 py-2.5 text-terminal-dim">{shortDate(a.created_at)}</td>
                <td className="px-4 py-2.5 text-terminal-dim">
                  {a.last_triggered_at ? (
                    <span title={a.last_message ?? ''} className="text-terminal-accent">
                      {shortDate(a.last_triggered_at)} — {a.last_message}
                    </span>
                  ) : (
                    'never'
                  )}
                </td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={() => deleteAlert.mutate(a.id)}
                    className="text-[10px] font-semibold tracking-wider text-rich uppercase hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {alerts?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-terminal-faint">
                  No alerts configured
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
