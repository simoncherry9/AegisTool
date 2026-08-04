import { api } from './client'

export interface DictionaryInfo {
  name: string
  path: string
  size_bytes: number
  line_count: number | null
  compressed: boolean
  custom: boolean
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
  error_message: string | null
}

export interface AnalyzePlan {
  plan: {
    job_id: number
    artifact_id: number
    hash_file_path: string
    max_total_time: number
    stages: Array<{
      mode: string
      tool?: string
      dictionary_path: string | null
      rules_path: string | null
      mask: string | null
      timeout_seconds: number | null
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
  createDictionary: (name: string, words: string[]) =>
    api.post<DictionaryInfo>('/cracking/dictionaries/custom', { name, words }),
  decompressDictionary: (path: string) =>
    api.post<DictionaryInfo>('/cracking/dictionaries/decompress', { path }),
  deleteDictionary: (name: string) =>
    api.delete<void>('/cracking/dictionaries/custom/' + encodeURIComponent(name)),
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

  startJob: (jobId: number, engagementId: number, preferredDicts?: string[], preferredRules?: string[]) => {
    const params = new URLSearchParams({ engagement_id: String(engagementId) })
    preferredDicts?.forEach(path => params.append('preferred_dicts', path))
    preferredRules?.forEach(path => params.append('preferred_rules', path))
    return api.post<{ job_id: number; status: string }>(`/cracking/jobs/${jobId}/start?${params}`)
  },
  cancelJob: (jobId: number) =>
    api.post<{ status: string }>('/cracking/jobs/' + jobId + '/cancel'),
  hashInfo: (artifactId: number) =>
    api.get<HashInfo>('/cracking/handshakes/' + artifactId + '/hashinfo'),
}
