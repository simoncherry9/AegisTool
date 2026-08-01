import { api } from './client'

export const handshakeApi = {
  startCapture: (data: any) => api.post('/handshake/capture', data),
  listCaptures: () => api.get('/handshake/captures'),
  getCapture: (id: string) => api.get(`/handshake/captures/${id}`),
  stopCapture: (id: string) => api.post(`/handshake/captures/${id}/stop`),
}
