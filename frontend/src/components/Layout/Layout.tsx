import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="layout">
      <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />
      {menuOpen && <button className="sidebar-scrim" aria-label="Cerrar navegación" onClick={() => setMenuOpen(false)} />}
      <div className="main-area">
        <Header onMenu={() => setMenuOpen(true)} />
        <div className="content">
          <div className="content-wide">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  )
}
