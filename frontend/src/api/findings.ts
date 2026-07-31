import { api } from './client'

export interface FindingRead {
  id: number
  engagement_id: number
  title: string
  category: string
  rule_id: string | null
  severity: string
  confidence: number | null
  description: string | null
  impact: string | null
  evidence: Record<string, unknown>
  remediation: string | null
  affected_assets: string[]
  status: string
  created_at: string | null
}

export interface FindingSummary {
  engagement_id: number
  total: number
  by_severity: Record<string, number>
  by_category: Record<string, number>
  by_status: Record<string, number>
  open_critical: number
  open_high: number
  open_medium: number
  open_low: number
  open_info: number
}

export interface FindingCreate {
  engagement_id: number
  title: string
  category: string
  severity: string
  rule_id?: string
  description?: string
  impact?: string
  remediation?: string
  affected_assets?: string[]
}

export interface FindingRule {
  rule_id: string
  title: string
  category: string
  severity: string
  description: string | null
}

export const findingsApi = {
  list: (params?: { engagement_id?: number; severity?: string; category?: string; status?: string }) =>
    api.get<FindingRead[]>('/findings' + (params ? '?' + new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([_, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString() : '')),
  get: (id: number) => api.get<FindingRead>('/findings/' + id),
  create: (data: FindingCreate) => api.post<FindingRead>('/findings', data),
  update: (id: number, data: Partial<{ title: string; description: string; impact: string; remediation: string; severity: string; status: string }>) =>
    api.patch<FindingRead>('/findings/' + id, data),
  delete: (id: number) => api.delete<void>('/findings/' + id),
  summary: (engagementId: number) =>
    api.get<FindingSummary>('/findings/summary?engagement_id=' + engagementId),
  rules: () => api.get<FindingRule[]>('/findings/rules'),
  runEngine: (engagementId?: number) =>
    api.post<{ total_findings: number; new_findings: number; findings: FindingRead[]; errors: string[] }>(
      '/findings/engine/run' + (engagementId ? '?engagement_id=' + engagementId : '')
    ),
}
