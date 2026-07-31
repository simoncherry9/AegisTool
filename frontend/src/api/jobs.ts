import { api } from './client'

export interface JobListItem {
  id: number
  engagement_id: number
  kind: string
  status: string
  progress: number | null
  created_at: string
  finished_at: string | null
}

export interface JobDetail {
  id: number
  engagement_id: number
  kind: string
  status: string
  progress: number | null
  message: string | null
  error: string | null
  result: Record<string, unknown> | null
  metadata: Record<string, unknown> | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface JobCreate {
  engagement_id: number
  kind: string
  metadata?: Record<string, unknown>
}

export interface JobEvent {
  id: number
  job_id: number
  event_type: string
  message: string | null
  data: Record<string, unknown> | null
  timestamp: string
}

export interface QueueStatus {
  queue_size: number
  active_workers: number
  pending_jobs: number
  running_jobs: number
}

export const jobsApi = {
  /** Listar trabajos del sistema */
  list: (params?: { engagement_id?: number; status?: string; kind?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) q.set(k, String(v))
      })
    }
    const qs = q.toString()
    return api.get<JobListItem[]>('/jobs' + (qs ? '?' + qs : ''))
  },

  /** Obtener detalle de un trabajo */
  get: (id: number) => api.get<JobDetail>(`/jobs/${id}`),

  /** Crear un trabajo */
  create: (data: JobCreate) => api.post<JobDetail>('/jobs', data),

  /** Actualizar un trabajo */
  update: (id: number, data: Partial<{ status: string; message: string; progress: number }>) =>
    api.patch<JobDetail>(`/jobs/${id}`, data),

  /** Cancelar un trabajo */
  cancel: (id: number, message?: string) =>
    api.post<JobDetail>(`/jobs/${id}/cancel`, message ? { message } : undefined),

  /** Reintentar un trabajo fallido */
  retry: (id: number) => api.post<JobDetail>(`/jobs/${id}/retry`),

  /** Obtener eventos de un trabajo */
  events: (id: number) => api.get<JobEvent[]>(`/jobs/${id}/events`),

  /** Estado de la cola de trabajos */
  queueStatus: () => api.get<QueueStatus>('/jobs/queue/status'),
}
