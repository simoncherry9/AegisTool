import { api } from './client'

export interface User {
  id: number
  username: string
  email: string
  full_name: string
  role: 'ADMIN' | 'OPERATOR' | 'AUDITOR'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserCreatePayload {
  username: string
  email: string
  full_name: string
  password: string
  role: 'ADMIN' | 'OPERATOR' | 'AUDITOR'
}

export interface UserUpdatePayload {
  full_name?: string
  email?: string
  role?: 'ADMIN' | 'OPERATOR' | 'AUDITOR'
  is_active?: boolean
  password?: string
}

export const usersApi = {
  list: () => api.get<User[]>('/users'),
  get: (id: number) => api.get<User>(`/users/${id}`),
  create: (data: UserCreatePayload) => api.post<User>('/users', data),
  update: (id: number, data: UserUpdatePayload) => api.patch<User>(`/users/${id}`, data),
}
