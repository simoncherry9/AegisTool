import { NavLink } from 'react-router-dom'

const ICONS = {
  dashboard: 'M4 13h6V4H4v9zm0 7h6v-4H4v4zm10 0h6v-9h-6v9zm0-13h6V4h-6v3z',
  engagements: 'M7 4h10a2 2 0 012 2v14H5V6a2 2 0 012-2zm2 4h6m-6 4h6m-6 4h4',
  discovery: 'M12 20a8 8 0 100-16 8 8 0 000 16zm5.7-2.3L21 21M12 8v4l3 2',
  degraded: 'M12 9v4m0 4h.01M5.1 20h13.8a2 2 0 001.7-3L13.7 5a2 2 0 00-3.4 0L3.4 17a2 2 0 001.7 3z',
  handshake: 'M7 11V8a5 5 0 0110 0v3m-9 10h8a3 3 0 003-3v-4a3 3 0 00-3-3H8a3 3 0 00-3 3v4a3 3 0 003 3z',
  validation: 'M7 12l3 3 7-7m4 4a9 9 0 11-18 0 9 9 0 0118 0z',
  active: 'M13 2L4 14h7l-1 8 9-13h-7l1-7z',
  wps: 'M5 12.5a10 10 0 0114 0M8.5 16a5 5 0 017 0M12 20h.01',
  cracking: 'M8 11V8a4 4 0 118 0v3m-9 10h10a2 2 0 002-2v-6a2 2 0 00-2-2H7a2 2 0 00-2 2v6a2 2 0 002 2zm5-7v4',
  resources: 'M4 5a2 2 0 012-2h11a2 2 0 012 2v16H6a2 2 0 01-2-2V5zm4 2h7m-7 4h7m-7 4h5',
  findings: 'M12 3l9 16H3L12 3zm0 6v4m0 3h.01',
  reports: 'M6 3h9l4 4v14H6V3zm8 0v5h5M9 13h6m-6 4h6',
  evidence: 'M7 3h7l5 5v13H7V3zm7 0v6h5M10 14h6m-6 3h4',
  jobs: 'M4 7h16v13H4V7zm5 0V4h6v3m-6 6h6',
  users: 'M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2m7-10a4 4 0 100-8 4 4 0 000 8zm7 0a4 4 0 014 4v2m-3-10a4 4 0 010 8',
  interfaces: 'M5 12.5a10 10 0 0114 0M8.5 16a5 5 0 017 0M12 20h.01M2 9a14 14 0 0120 0',
  tools: 'M14.7 6.3a4 4 0 01-5 5L4 17l3 3 5.7-5.7a4 4 0 005-5L15 12l-3-3 2.7-2.7z',
}

const NAV_ITEMS = [
  { section: 'Workspace', items: [
    { to: '/', label: 'Vista general', icon: ICONS.dashboard },
    { to: '/engagements', label: 'Engagements', icon: ICONS.engagements },
  ]},
  { section: 'Reconocimiento', items: [
    { to: '/discovery', label: 'Discovery', icon: ICONS.discovery },
    { to: '/discovery/degraded', label: 'APs degradados', icon: ICONS.degraded },
    { to: '/handshakes', label: 'Handshakes', icon: ICONS.handshake },
    { to: '/validation', label: 'Validación', icon: ICONS.validation },
  ]},
  { section: 'Evaluación activa', items: [
    { to: '/deauth', label: 'Deauth', icon: ICONS.active },
    { to: '/wps', label: 'WPS', icon: ICONS.wps },
    { to: '/cracking', label: 'Cracking', icon: ICONS.cracking },
    { to: '/cracking/resources', label: 'Recursos', icon: ICONS.resources },
  ]},
  { section: 'Resultados', items: [
    { to: '/findings', label: 'Hallazgos', icon: ICONS.findings },
    { to: '/evidence', label: 'Evidencia', icon: ICONS.evidence },
    { to: '/reports', label: 'Informes', icon: ICONS.reports },
  ]},
  { section: 'Administración', items: [
    { to: '/jobs', label: 'Trabajos', icon: ICONS.jobs },
    { to: '/interfaces', label: 'Interfaces', icon: ICONS.interfaces },
    { to: '/tools', label: 'Herramientas', icon: ICONS.tools },
    { to: '/users', label: 'Usuarios', icon: ICONS.users },
  ]},
]

interface SidebarProps {
  open: boolean
  onNavigate: () => void
}

export function Sidebar({ open, onNavigate }: SidebarProps) {
  return (
    <aside className={`sidebar${open ? ' open' : ''}`} aria-label="Navegación principal">
      <div className="sidebar-brand">
        <div className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M12 2.5l8 3.2v5.8c0 5-3.2 8.2-8 10-4.8-1.8-8-5-8-10V5.7L12 2.5z" />
            <path d="M8.5 13.5a5 5 0 017 0M10.5 16a2 2 0 013 0M12 18.5h.01" />
          </svg>
        </div>
        <div className="brand-copy"><strong>AegisWiFi</strong><span>Security operations</span></div>
        <button className="sidebar-close" onClick={onNavigate} aria-label="Cerrar navegación">×</button>
      </div>

      <div className="workspace-status">
        <div className="workspace-status-top"><span>Entorno local</span><span className="status-live">Operativo</span></div>
        <div className="workspace-status-meta"><span className="system-dot" /> API protegida en localhost</div>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((section) => (
          <div key={section.section} className="sidebar-section">
            <div className="sidebar-section-title">{section.section}</div>
            {section.items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === '/' || item.to === '/discovery'}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`} onClick={onNavigate}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d={item.icon} />
                </svg>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer"><span>AegisWiFi</span><span>v0.1.0</span></div>
    </aside>
  )
}
