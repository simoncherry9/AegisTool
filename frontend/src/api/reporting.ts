import { api } from './client'

export const reportingApi = {
  generate: (data: any) => api.post('/reports/generate', data),
  list: () => api.get('/reports'),
  get: (id: string) => api.get(`/reports/${id}`),
  download: (id: string) => api.get(`/reports/${id}/download`),
}
