import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/engagements': 'Engagements',
  '/discovery': 'Discovery',
  '/handshakes': 'Handshakes',
  '/cracking': 'Cracking',
  '/findings': 'Hallazgos',
  '/users': 'Gestión de Usuarios',
  '/interfaces': 'Interfaces de Red',
  '/tools': 'Herramientas del Sistema',
}

export function Header({ onMenu }: { onMenu: () => void }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const base = '/' + (location.pathname.split('/')[1] || '')
  const title = PAGE_TITLES[base] ?? PAGE_TITLES['/']

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="header flex-between">
      <div className="header-context">
        <button className="mobile-menu" onClick={onMenu} aria-label="Abrir navegación">
          <span /><span /><span />
        </button>
        <div>
        <div className="header-title">{title}</div>
        <div className="header-subtitle">Centro de operaciones inalámbricas</div>
        </div>
      </div>
      {user && (
        <div className="user-profile-badge">
          <div className="user-info">
            <span className="user-name">{user.full_name || user.username}</span>
            <span className={`badge badge-role-${user.role.toLowerCase()}`}>{user.role}</span>
          </div>
          <button className="btn-logout" onClick={handleLogout} title="Cerrar sesión" aria-label="Cerrar sesión">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      )}
    </header>
  )
}
