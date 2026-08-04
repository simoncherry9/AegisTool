import { api } from './client'

export interface CaptureListItem {
  id: number
  engagement_id: number
  job_id: number | null
  category: string
  format: string
  sha256: string | null
  original_filename: string | null
  size_bytes: number | null
  tool: string | null
  created_at: string
}

export interface CaptureDetail {
  id: number
  engagement_id: number
  job_id: number | null
  category: string
  path: string
  format: string
  sha256: string | null
  original_filename: string | null
  size_bytes: number | null
  interface: string | null
  channel: number | null
  bssid: string | null
  ssid: string | null
  tool: string | null
  tool_version: string | null
  metadata: Record<string, unknown>
  derived_from_id: number | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export const evidenceApi = {
  /** Listar evidencia */
  list: (params?: { engagement_id?: number; job_id?: number; category?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) q.set(k, String(v))
      })
    }
    const qs = q.toString()
    return api.get<CaptureListItem[]>('/evidence' + (qs ? '?' + qs : ''))
  },

  /** Obtener detalle de evidencia */
  get: (id: number) => api.get<CaptureDetail>(`/evidence/${id}`),

  /** Descargar archivo de evidencia */
  downloadUrl: (id: number) => `/api/v1/evidence/${id}/download`,

  /** Descargar archivo de evidencia como blob */
  download: (id: number) => {
    const url = '/api/v1/evidence/' + id + '/download'
    const token = localStorage.getItem('aegis_token')
    return fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} }).then(r => {
      if (!r.ok) throw new Error('Error al descargar: ' + r.status)
      return r.blob()
    })
  },
}
