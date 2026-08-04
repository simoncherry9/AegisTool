import { api } from './client'

export interface ValidationRequest {
  capture_id?: number | null
  file_path?: string | null
  engagement_id?: number | null
  force_reprocess?: boolean
}

export interface ValidationResult {
  artifact_id: number | null
  capture_id: number | null
  quality: string
  quality_score: number
  validated: boolean
  hash22000_path: string | null
  kind: string
  message_pair: string | null
  warnings: string[]
  errors: string[]
}

export interface HandshakeReport {
  id: number
  bssid: string | null
  ssid: string | null
  channel: number | null
  kind: string
  quality: string
  validated: boolean
  message_pair: string | null
  hash_file: string | null
  crack_status: string | null
  access_point_id: number | null
  station_mac: string | null
  created_at: string | null
  engagement_id?: number | null
}

export const validationApi = {
  validate: (req: ValidationRequest) =>
    api.post<{ result: ValidationResult }>('/validation/validate', req),

  artifacts: (params?: { capture_id?: number; quality?: string; validated?: boolean }) => {
    const q = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) q.set(k, String(v))
      })
    }
    const qs = q.toString()
    return api.get<HandshakeReport[]>('/validation/artifacts' + (qs ? '?' + qs : ''))
  },

  artifact: (id: number) => api.get<HandshakeReport>('/validation/artifacts/' + id),

  reprocess: (id: number) =>
    api.post<{ result: ValidationResult }>('/validation/reprocess/' + id),
}
