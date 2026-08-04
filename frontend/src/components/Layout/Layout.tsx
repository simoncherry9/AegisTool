import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="layout">
      <a className="skip-link" href="#main-content">Saltar al contenido</a>
      <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />
      {menuOpen && <button className="sidebar-scrim" aria-label="Cerrar navegación" onClick={() => setMenuOpen(false)} />}
      <div className="main-area">
        <Header onMenu={() => setMenuOpen(true)} />
        <main className="content" id="main-content">
          <div className="content-wide">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
