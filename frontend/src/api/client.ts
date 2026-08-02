const BASE = '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem('aegis_token')
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders, ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/login')) {
      localStorage.removeItem('aegis_token')
      localStorage.removeItem('aegis_user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    const body = await res.text().catch(() => '')
    let message = body || res.statusText
    try {
      const parsed = JSON.parse(body)
      if (parsed.detail) {
        if (Array.isArray(parsed.detail)) {
          message = parsed.detail.map((e: any) => `${e.loc?.join('.') || 'field'}: ${e.msg}`).join(', ')
        } else if (typeof parsed.detail === 'string') {
          message = parsed.detail
        } else {
          message = JSON.stringify(parsed.detail)
        }
      }
    } catch { /* body is not JSON, use as-is */ }
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
