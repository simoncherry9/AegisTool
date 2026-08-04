import { api } from './client'

export interface ToolInfo {
  name: string
  binary: string
  installed: boolean
  version: string | null
  description: string
  category: string
}

export interface ToolsCheckResult {
  tools: ToolInfo[]
  total: number
  installed: number
  missing: number
  os: string
}

export interface SudoStatus {
  configured: boolean
  masked: string | null
}

export interface SudoConfigResult {
  status: string
  message: string
}

export const toolsApi = {
  check: () => api.get<ToolsCheckResult>('/tools/check'),
  sudoStatus: () => api.get<SudoStatus>('/tools/sudo-status'),
  configureSudo: (password: string) =>
    api.post<SudoConfigResult>('/tools/sudo-config', { password }),
}
