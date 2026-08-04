import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { api, ApiError } from '../../api/client'
import { User } from '../../api/users'

interface LoginResponse { access_token: string; token_type: string; user: User }

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const response = await api.post<LoginResponse>('/auth/login', { username, password })
      login(response.access_token, response.user)
      navigate('/')
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        try { setError(JSON.parse(requestError.message).detail || 'Error de autenticación') }
        catch { setError(requestError.message || 'Credenciales inválidas') }
      } else { setError('No se pudo conectar con el servidor') }
    } finally { setLoading(false) }
  }

  return (
    <main className="login-container">
      <section className="login-showcase" aria-label="Presentación de AegisWiFi">
        <div className="login-showcase-inner">
          <div className="login-brand"><div className="brand-mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 2.5l8 3.2v5.8c0 5-3.2 8.2-8 10-4.8-1.8-8-5-8-10V5.7L12 2.5z" /><path d="M8.5 13.5a5 5 0 017 0M10.5 16a2 2 0 013 0M12 18.5h.01" /></svg></div><strong>AegisWiFi</strong></div>
          <div className="showcase-copy"><span className="eyebrow">Wireless security workspace</span><h1>Control total de cada auditoría inalámbrica.</h1><p>Reconocimiento, validación, evidencia y reportes en un entorno operacional diseñado para equipos de seguridad.</p></div>
          <div className="showcase-features"><div><span>01</span><p><strong>Alcance primero</strong>Políticas aplicadas antes de cada acción.</p></div><div><span>02</span><p><strong>Evidencia trazable</strong>Integridad y cadena de custodia.</p></div><div><span>03</span><p><strong>Operación local</strong>Superficie de exposición reducida.</p></div></div>
          <div className="showcase-status"><span className="system-dot" /> Sistema local listo para operar</div>
        </div>
      </section>
      <section className="login-access">
        <div className="login-card">
          <div className="login-header"><span className="login-overline">Acceso seguro</span><h2>Bienvenido de nuevo</h2><p>Ingresa tus credenciales para abrir el workspace.</p></div>
          {error && <div className="login-alert error" role="alert"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M12 8v5m0 3h.01" /></svg><span>{error}</span></div>}
          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group"><label htmlFor="username">Usuario</label><div className="input-with-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></svg><input id="username" type="text" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Tu nombre de usuario" required autoComplete="username" autoFocus /></div></div>
            <div className="form-group"><label htmlFor="password">Contraseña</label><div className="input-with-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="11" width="18" height="10" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" /></svg><input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Ingresa tu contraseña" required autoComplete="current-password" /></div></div>
            <button type="submit" className="login-btn" disabled={loading}>{loading ? <><span className="button-spinner" /> Verificando acceso...</> : <>Ingresar al workspace <span>→</span></>}</button>
          </form>
          <div className="login-footer"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 11V8a5 5 0 0110 0v3m-9 10h8a3 3 0 003-3v-4a3 3 0 00-3-3H8a3 3 0 00-3 3v4a3 3 0 003 3z" /></svg> Acceso restringido a personal autorizado</div>
        </div>
      </section>
    </main>
  )
}
