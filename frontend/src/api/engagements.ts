import { api } from './client'

export interface Engagement {
  id: number
  code: string
  name: string
  client: string
  operator: string
  status: string
  start_date: string | null
  end_date: string | null
  created_at: string
}

export interface EngagementCreate {
  name: string
  client: string
  operator: string
}

export const engagementsApi = {
  list: () => api.get<Engagement[]>('/engagements'),
  get: (id: number) => api.get<Engagement>(`/engagements/${id}`),
  create: (data: EngagementCreate) => api.post<Engagement>('/engagements', data),
  activate: (id: number) => api.post<Engagement>(`/engagements/${id}/activate`),
  close: (id: number) => api.post<Engagement>(`/engagements/${id}/close`),
  complete: (id: number) => api.post<Engagement>(`/engagements/${id}/complete`),
}
