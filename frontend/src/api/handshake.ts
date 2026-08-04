import { api } from './client'

export interface HandshakeCaptureRequest {
  engagement_id: number
  interface: string
  bssid: string
  channel?: number | null
  duration: number
  deauth_assisted: boolean
  deauth_count: number
}

export const handshakeApi = {
  startCapture: (data: HandshakeCaptureRequest) => api.post('/handshake/capture', data),
  listCaptures: () => api.get('/handshake/captures'),
  getCapture: (id: string) => api.get(`/handshake/captures/${id}`),
  stopCapture: (id: string) => api.post(`/handshake/captures/${id}/stop`),
}
