import { api } from './client'

export type ReportFormat = 'html' | 'pdf' | 'json'

export interface ReportRequest {
  engagement_id: number
  format: ReportFormat
  include_executive_summary: boolean
  include_findings: boolean
  include_evidence: boolean
  include_methodology: boolean
}

export interface ReportItem {
  id: string
  engagement_id: number
  format: ReportFormat
  status: 'PENDING' | 'GENERATING' | 'COMPLETE' | 'FAILED'
  created_at: string
  completed_at?: string | null
  file_size?: number | null
  error?: string | null
}

export const reportingApi = {
  generate: (data: ReportRequest) => api.post<ReportItem>('/reports/generate', data),
  list: () => api.get<ReportItem[]>('/reports'),
  get: (id: string) => api.get<ReportItem>(`/reports/${id}`),
  download: (id: string) => {
    const token = localStorage.getItem('aegis_token')
    return fetch(`/api/v1/reports/${id}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).then(response => {
      if (!response.ok) throw new Error(`No se pudo descargar el informe (${response.status})`)
      return response.blob()
    })
  },
}
