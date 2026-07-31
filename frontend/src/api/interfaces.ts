import { api } from './client'

export interface WirelessInterface {
  name: string
  type: string
  phy: number | null
  mac: string | null
  driver: string | null
  state: string
  mode: string
  channel: number | null
  frequency: number | null
  band: string | null
  signal: number | null
  tx_power: number | null
  monitor_mode: boolean
  capabilities: string[]
}

export interface InterfacePrepareResult {
  name: string
  success: boolean
  mode: string | null
  injection_test: boolean | null
  error: string | null
}

export interface InterfaceRestoreResult {
  name: string
  success: boolean
  restored_state: string | null
  error: string | null
}

export interface InterfaceDiagnostic {
  rfkill: unknown[]
  conflicting_processes: unknown[]
  health: string
  errors: string[]
  warnings: string[]
}

export const interfacesApi = {
  /** Listar todas las interfaces inalámbricas */
  list: () => api.get<WirelessInterface[]>('/interfaces'),

  /** Obtener detalle de una interfaz */
  get: (name: string) => api.get<WirelessInterface>(`/interfaces/${name}`),

  /** Preparar interfaz para auditoría (monitor mode) */
  prepare: (name: string) =>
    api.post<InterfacePrepareResult>(`/interfaces/${name}/prepare`),

  /** Restaurar interfaz a estado original */
  restore: (name: string) =>
    api.post<InterfaceRestoreResult>(`/interfaces/${name}/restore`),

  /** Diagnóstico del sistema de interfaces */
  diagnose: (name?: string) =>
    api.get<InterfaceDiagnostic>('/interfaces/diagnose' + (name ? `?name=${name}` : '')),
}
