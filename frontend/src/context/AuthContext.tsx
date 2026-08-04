import React, { createContext, useContext, useState, useEffect } from 'react'
import { api } from '../api/client'
import { User } from '../api/users'

interface AuthContextType {
  user: User | null
  token: string | null
  login: (token: string, user: User) => void
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('aegis_token'))
  const [user, setUser] = useState<User | null>(() => {
    const cached = localStorage.getItem('aegis_user')
    if (!cached) return null
    try {
      return JSON.parse(cached) as User
    } catch {
      localStorage.removeItem('aegis_user')
      return null
    }
  })

  useEffect(() => {
    if (token && !user) {
      api.get<User>('/auth/me')
        .then((u) => {
          setUser(u)
          localStorage.setItem('aegis_user', JSON.stringify(u))
        })
        .catch(() => {
          logout()
        })
    }
  }, [token, user])

  const login = (newToken: string, newUser: User) => {
    setToken(newToken)
    setUser(newUser)
    localStorage.setItem('aegis_token', newToken)
    localStorage.setItem('aegis_user', JSON.stringify(newUser))
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('aegis_token')
    localStorage.removeItem('aegis_user')
  }

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth debe usarse dentro de un AuthProvider')
  }
  return context
}
