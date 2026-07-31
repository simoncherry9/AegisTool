import { useLocation } from 'react-router-dom'

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/engagements': 'Engagements',
  '/discovery': 'Discovery',
  '/handshakes': 'Handshakes',
  '/cracking': 'Cracking',
  '/findings': 'Hallazgos',
}

export function Header() {
  const location = useLocation()
  const base = '/' + location.pathname.split('/')[1]
  const title = PAGE_TITLES[base] ?? PAGE_TITLES['/']

  return (
    <header className="header">
      <div className="header-title">{title}</div>
      <div className="header-subtitle">AegisWiFi — Plataforma de auditoría inalámbrica</div>
    </header>
  )
}
