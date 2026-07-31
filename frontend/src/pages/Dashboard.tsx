import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StatusBadge } from '../components/StatusBadge'
import { SeverityBadge } from '../components/SeverityBadge'
import { engagementsApi, type Engagement } from '../api/engagements'
import { findingsApi, type FindingSummary } from '../api/findings'
import { crackingApi, type CrackingJob } from '../api/cracking'

interface DashboardData {
  engagements: Engagement[]
  summary: FindingSummary | null
  crackingJobs: CrackingJob[]
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [engagements, recentFindings, crackingJobs] = await Promise.all([
          engagementsApi.list(),
          findingsApi.list({ limit: '5' } as any).catch(() => []),
          crackingApi.jobs().catch(() => []),
        ])
        const activeEng = engagements.find((e) => e.status === 'ACTIVE')
        const summary = activeEng
          ? await findingsApi.summary(activeEng.id).catch(() => null)
          : null
        setData({ engagements, summary, crackingJobs } as DashboardData)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <LoadingSpinner text="Cargando dashboard..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>

  const activeEngagements = data?.engagements?.filter((e) => e.status === 'ACTIVE') ?? []
  const criticalOpen = data?.summary?.open_critical ?? 0
  const highOpen = data?.summary?.open_high ?? 0
  const openJobs = data?.crackingJobs?.filter((j) => j.status === 'RUNNING' || j.status === 'QUEUED') ?? []

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-4" style={{ marginBottom: 32 }}>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: 'var(--accent)' }}>{data?.engagements?.length ?? 0}</div>
          <div className="stat-label">Engagements</div>
          <div className="stat-trend up">{activeEngagements.length} activos</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: criticalOpen > 0 ? 'var(--red)' : 'var(--green)' }}>{criticalOpen}</div>
          <div className="stat-label">Críticos abiertos</div>
          <div className="stat-trend" style={{ color: highOpen > 0 ? 'var(--orange)' : 'var(--text-muted)' }}>
            {highOpen} altos
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: 'var(--yellow)' }}>{data?.summary?.total ?? 0}</div>
          <div className="stat-label">Hallazgos totales</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: openJobs.length > 0 ? 'var(--accent)' : 'var(--text-muted)' }}>{openJobs.length}</div>
          <div className="stat-label">Trabajos activos</div>
          <div className="stat-trend up">{data?.crackingJobs?.length ?? 0} totales</div>
        </div>
      </div>

      {/* Getting started — solos cuando no hay actividad */}
      {data?.engagements?.length === 0 && (
        <div className="card" style={{ marginBottom: 24, background: 'linear-gradient(135deg, var(--bg-card), var(--bg-secondary))' }}>
          <div style={{ textAlign: 'center', padding: '32px 16px' }}>
            <h2 style={{ marginBottom: 8 }}>Bienvenido a AegisWiFi</h2>
            <p style={{ color: 'var(--text-muted)', maxWidth: 480, margin: '0 auto 24px' }}>
              Plataforma profesional de auditoria de redes inalambricas.
              Sigue estos pasos para comenzar:
            </p>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
              <div className="card" style={{ padding: 16, minWidth: 160, textAlign: 'center' }}>
                <div style={{ fontSize: 28, marginBottom: 4 }}>1</div>
                <strong>Crear engagement</strong>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Define el alcance de la auditoria</div>
              </div>
              <div className="card" style={{ padding: 16, minWidth: 160, textAlign: 'center' }}>
                <div style={{ fontSize: 28, marginBottom: 4 }}>2</div>
                <strong>Descubrir redes</strong>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Escanea puntos de acceso y clientes</div>
              </div>
              <div className="card" style={{ padding: 16, minWidth: 160, textAlign: 'center' }}>
                <div style={{ fontSize: 28, marginBottom: 4 }}>3</div>
                <strong>Validar handshakes</strong>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Captura y valida credenciales</div>
              </div>
              <div className="card" style={{ padding: 16, minWidth: 160, textAlign: 'center' }}>
                <div style={{ fontSize: 28, marginBottom: 4 }}>4</div>
                <strong>Auditar hallazgos</strong>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Revisa resultados y genera informes</div>
              </div>
            </div>
            <div style={{ marginTop: 20 }}>
              <a href="/engagements/new" className="btn btn-primary">Crear mi primer engagement</a>
              <span style={{ margin: '0 8px', color: 'var(--text-muted)' }}>o</span>
              <a href="/tools" className="btn btn-secondary">Verificar herramientas</a>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-2">
        {/* Active engagements */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Engagements activos</div>
              <div className="card-subtitle">Auditorías en curso</div>
            </div>
            <Link to="/engagements" className="btn btn-sm btn-secondary">Ver todos</Link>
          </div>
          {activeEngagements.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)' }}>
              <p>No hay engagements activos</p>
              <Link to="/engagements/new" className="btn btn-primary" style={{ marginTop: 12 }}>
                Crear engagement
              </Link>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr><th>Código</th><th>Cliente</th><th>Estado</th></tr>
                </thead>
                <tbody>
                  {activeEngagements.map((e) => (
                    <tr key={e.id} className="clickable" onClick={() => window.location.href = `/engagements/${e.id}`}>
                      <td><Link to={`/engagements/${e.id}`} style={{ fontWeight: 600 }}>{e.code}</Link></td>
                      <td>{e.client}</td>
                      <td><StatusBadge status={e.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Active jobs */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Cracking jobs</div>
              <div className="card-subtitle">Últimos trabajos</div>
            </div>
            <Link to="/cracking" className="btn btn-sm btn-secondary">Ver todos</Link>
          </div>
          {!data?.crackingJobs?.length ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)' }}>
              <p>No hay trabajos de cracking</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr><th>#</th><th>Estrategia</th><th>Estado</th><th>Progreso</th></tr>
                </thead>
                <tbody>
                  {data.crackingJobs.slice(0, 5).map((j) => (
                    <tr key={j.id} className="clickable" onClick={() => window.location.href = `/cracking/${j.id}`}>
                      <td><Link to={`/cracking/${j.id}`}>#{j.id}</Link></td>
                      <td>{j.strategy}</td>
                      <td><StatusBadge status={j.status} /></td>
                      <td>{j.progress != null ? `${(j.progress * 100).toFixed(0)}%` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
