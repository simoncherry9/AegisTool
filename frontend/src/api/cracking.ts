import { api } from './client'

export interface DictionaryInfo {
  name: string
  path: string
  size_bytes: number
  line_count: number | null
}

export interface RuleInfo {
  name: string
  path: string
  size_bytes: number
  rule_count: number | null
}

export interface CrackingJob {
  id: number
  artifact_id: number
  strategy: string
  status: string
  progress: number | null
  speed: number | null
  recovered: boolean
  keyspace: number | null
  started_at: string | null
  finished_at: string | null
}

export interface AnalyzePlan {
  plan: {
    job_id: number
    artifact_id: number
    hash_file: string
    stages: Array<{
      mode: string
      dict: string | null
      rule: string | null
      priority: number
      estimated_time: number
    }>
  }
  hash_info: {
    hash_line: string
    bssid: string | null
    ssid: string | null
  } | null
  warnings: string[]
}

export interface HashInfo {
  hash_line: string
  bssid: string | null
  ssid: string | null
}

export const crackingApi = {
  dictionaries: () => api.get<DictionaryInfo[]>('/cracking/dictionaries'),
  rules: () => api.get<RuleInfo[]>('/cracking/rules'),

  analyze: (artifactId: number, preferredDicts?: string[], preferredRules?: string[]) => {
    let url = '/cracking/analyze/' + artifactId
    const params = new URLSearchParams()
    if (preferredDicts?.length) preferredDicts.forEach(d => params.append('preferred_dicts', d))
    if (preferredRules?.length) preferredRules.forEach(r => params.append('preferred_rules', r))
    const qs = params.toString()
    if (qs) url += '?' + qs
    return api.post<AnalyzePlan>(url)
  },

  jobs: (engagementId?: number) =>
    api.get<CrackingJob[]>('/cracking/jobs' + (engagementId ? '?engagement_id=' + engagementId : '')),
  job: (id: number) => api.get<CrackingJob>('/cracking/jobs/' + id),

  createJob: (artifactId: number, strategy?: string, engagementId?: number) => {
    let url = '/cracking/jobs?artifact_id=' + artifactId + '&strategy=' + (strategy ?? 'dictionary')
    if (engagementId) url += '&engagement_id=' + engagementId
    return api.post<CrackingJob>(url)
  },

  startJob: (jobId: number, engagementId: number) =>
    api.post<{ job_id: number; result: unknown }>('/cracking/jobs/' + jobId + '/start?engagement_id=' + engagementId),
  cancelJob: (jobId: number) =>
    api.post<{ status: string }>('/cracking/jobs/' + jobId + '/cancel'),
  hashInfo: (artifactId: number) =>
    api.get<HashInfo>('/cracking/handshakes/' + artifactId + '/hashinfo'),
}
