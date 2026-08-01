import { api } from './client'

export const pmkidApi = {
  startCapture: (data: any) => api.post('/pmkid/capture', data),
  listCaptures: () => api.get('/pmkid/captures'),
  getCapture: (id: string) => api.get(`/pmkid/captures/${id}`),
  stopCapture: (id: string) => api.post(`/pmkid/captures/${id}/stop`),
}
