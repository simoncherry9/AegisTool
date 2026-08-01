import { api } from './client'

export const wpsApi = {
  scan: (data?: any) => api.post('/wps/scan', data),
  attack: (data: any) => api.post('/wps/attack', data),
  attacks: () => api.get('/wps/attacks'),
  getAttack: (id: string) => api.get(`/wps/attacks/${id}`),
  stopAttack: (id: string) => api.post(`/wps/attacks/${id}/stop`),
}
