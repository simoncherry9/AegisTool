import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function Layout() {
  return (
    <div className="layout">
      <Sidebar />
      <div className="main-area">
        <Header />
        <div className="content">
          <div className="content-wide">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  )
}
