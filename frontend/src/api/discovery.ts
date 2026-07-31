import { api } from './client'

export interface AccessPoint {
  bssid: string
  ssid: string | null
  channel: number | null
  frequency: number | null
  band: string | null
  signal: number | null
  vendor: string | null
  protocol: string
  in_scope: boolean
  clients_count: number
  first_seen: string | null
  last_seen: string | null
  akm: string | null
  cipher: string | null
  pmf: string
  wps: boolean
  transition_mode: string
  wpa3_supported: boolean
  degraded: boolean
}

export interface ClientSummary {
  mac: string
  randomized: boolean
  vendor: string | null
  associated_bssid: string | null
  associated_ssid: string | null
  signal: number | null
  probe_requests: string[]
  first_seen: string | null
  last_seen: string | null
  controlled: boolean
}

export interface ScanConfig {
  interface: string
  channel?: number | null
  band?: string | null
  hop_interval?: number
  duration?: number | null
}

export interface ScanStatus {
  running: boolean
  interface: string | null
  channel: number | null
  uptime_seconds: number | null
  ap_count: number
  client_count: number
  started_at: string | null
  error: string | null
}

export const discoveryApi = {
  /** Iniciar escaneo */
  start: (config: ScanConfig) =>
    api.post<ScanStatus>('/discovery/scan/start', config),

  /** Detener escaneo */
  stop: () => api.post<ScanStatus>('/discovery/scan/stop'),

  /** Estado actual del escáner */
  status: () => api.get<ScanStatus>('/discovery/status'),

  /** Listar puntos de acceso detectados */
  accessPoints: (params?: {
    ssid?: string; bssid?: string; band?: string; channel?: number;
    protocol?: string; in_scope?: boolean; wps?: boolean;
    signal_min?: number; signal_max?: number;
    limit?: number; offset?: number;
  }) => {
    const q = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v != null) q.set(k, String(v))
      })
    }
    const qs = q.toString()
    return api.get<AccessPoint[]>('/discovery/aps' + (qs ? '?' + qs : ''))
  },

  /** Obtener detalle de un AP por BSSID */
  accessPoint: (bssid: string) =>
    api.get<AccessPoint>(`/discovery/aps/${bssid}`),

  /** Listar clientes/estaciones detectados */
  clients: () => api.get<ClientSummary[]>('/discovery/clients'),

  /** Snapshot completo del inventario */
  snapshot: () => api.get<{
    access_points: AccessPoint[]
    clients: ClientSummary[]
    scan_status: ScanStatus
    timestamp: string
  }>('/discovery/snapshot'),

  /** APs con seguridad degradada */
  degraded: () => api.get<AccessPoint[]>('/discovery/degraded'),
}
