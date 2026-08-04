import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const PAGE_META: Record<string, { title: string; section: string; description: string }> = {
  '/': { title: 'Vista general', section: 'Workspace', description: 'Estado operacional de la auditoría' },
  '/engagements': { title: 'Engagements', section: 'Workspace', description: 'Alcance, cliente y ciclo de vida' },
  '/discovery': { title: 'Discovery', section: 'Reconocimiento', description: 'Inventario inalámbrico en tiempo real' },
  '/handshakes': { title: 'Handshakes', section: 'Reconocimiento', description: 'Capturas y material de autenticación' },
  '/validation': { title: 'Validación', section: 'Reconocimiento', description: 'Control de calidad de capturas' },
  '/deauth': { title: 'Deauth', section: 'Evaluación activa', description: 'Pruebas de resiliencia autorizadas' },
  '/wps': { title: 'WPS', section: 'Evaluación activa', description: 'Evaluación de configuración WPS' },
  '/cracking': { title: 'Cracking', section: 'Evaluación activa', description: 'Análisis controlado de credenciales' },
  '/findings': { title: 'Hallazgos', section: 'Resultados', description: 'Riesgos, impacto y remediación' },
  '/evidence': { title: 'Evidencia', section: 'Resultados', description: 'Custodia y trazabilidad de artefactos' },
  '/reports': { title: 'Informes', section: 'Resultados', description: 'Entregables técnicos y ejecutivos' },
  '/jobs': { title: 'Trabajos', section: 'Administración', description: 'Ejecución y seguimiento de procesos' },
  '/users': { title: 'Usuarios', section: 'Administración', description: 'Accesos, roles y operadores' },
  '/interfaces': { title: 'Interfaces', section: 'Administración', description: 'Adaptadores y modos inalámbricos' },
  '/tools': { title: 'Herramientas', section: 'Administración', description: 'Disponibilidad del entorno de auditoría' },
}

export function Header({ onMenu }: { onMenu: () => void }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const base = '/' + (location.pathname.split('/')[1] || '')
  const meta = PAGE_META[base] ?? PAGE_META['/']
  const initials = (user?.full_name || user?.username || 'AW').split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="header">
      <div className="header-context">
        <button className="mobile-menu" onClick={onMenu} aria-label="Abrir navegación"><span /><span /><span /></button>
        <div>
          <div className="breadcrumbs"><span>{meta.section}</span><i>/</i><strong>{meta.title}</strong></div>
          <div className="header-subtitle">{meta.description}</div>
        </div>
      </div>
      {user && (
        <div className="header-actions">
          <div className="local-connection"><span className="system-dot" />Conexión local segura</div>
          <div className="user-profile-badge">
            <div className="user-avatar" aria-hidden="true">{initials}</div>
            <div className="user-info"><span className="user-name">{user.full_name || user.username}</span><span className="user-role">{user.role}</span></div>
            <button className="btn-logout" onClick={handleLogout} title="Cerrar sesión" aria-label="Cerrar sesión">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5m5 5H9" /></svg>
            </button>
          </div>
        </div>
      )}
    </header>
  )
}
