import type {
  AlertCreate,
  AlertOut,
  AlertTriggered,
  BondDetail,
  BondRow,
  CurveResponse,
  DashboardSummary,
  SearchResult,
} from './types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  bonds: () => request<BondRow[]>('/bonds'),
  bond: (cusip: string) => request<BondDetail>(`/bond/${cusip}`),
  dashboard: () => request<DashboardSummary>('/dashboard'),
  curves: () => request<CurveResponse>('/curves'),
  curveHistory: (tenors: string) =>
    request<Record<string, string | number>[]>(`/curves/history?tenors=${tenors}`),
  search: (q: string) => request<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`),
  alerts: () => request<AlertOut[]>('/alerts'),
  createAlert: (payload: AlertCreate) =>
    request<AlertOut>('/alerts', { method: 'POST', body: JSON.stringify(payload) }),
  deleteAlert: (id: number) => request<void>(`/alerts/${id}`, { method: 'DELETE' }),
  evaluateAlerts: () => request<AlertTriggered[]>('/alerts/evaluate', { method: 'POST' }),
}
