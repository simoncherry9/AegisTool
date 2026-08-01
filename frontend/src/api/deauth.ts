import { api } from './client'

export const deauthApi = {
  send: (data: any) => api.post('/deauth/send', data),
  history: () => api.get('/deauth/history'),
}
