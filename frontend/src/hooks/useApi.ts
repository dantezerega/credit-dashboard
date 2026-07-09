import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { AlertCreate } from '../api/types'

export const useBonds = () =>
  useQuery({ queryKey: ['bonds'], queryFn: api.bonds, staleTime: 60_000 })

export const useBondDetail = (cusip: string | undefined) =>
  useQuery({
    queryKey: ['bond', cusip],
    queryFn: () => api.bond(cusip!),
    enabled: !!cusip,
    staleTime: 60_000,
  })

export const useDashboard = () =>
  useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard, staleTime: 60_000 })

export const useCurve = () =>
  useQuery({ queryKey: ['curve'], queryFn: api.curves, staleTime: 300_000 })

export const useCurveHistory = (tenors = '2,5,10,30') =>
  useQuery({
    queryKey: ['curveHistory', tenors],
    queryFn: () => api.curveHistory(tenors),
    staleTime: 300_000,
  })

export const useSearch = (query: string) =>
  useQuery({
    queryKey: ['search', query],
    queryFn: () => api.search(query),
    enabled: query.trim().length > 0,
    staleTime: 30_000,
  })

export const useAlerts = () => useQuery({ queryKey: ['alerts'], queryFn: api.alerts })

export const useCreateAlert = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: AlertCreate) => api.createAlert(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
}

export const useDeleteAlert = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.deleteAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
}

export const useEvaluateAlerts = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.evaluateAlerts,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
}
