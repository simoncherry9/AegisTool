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

export const toolsApi = {
  check: () => api.get<ToolsCheckResult>('/tools/check'),
}
