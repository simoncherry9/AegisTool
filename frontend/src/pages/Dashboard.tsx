import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { StatusBadge } from '../components/StatusBadge'
import { engagementsApi, type Engagement } from '../api/engagements'
import { findingsApi, type FindingSummary } from '../api/findings'
import { crackingApi, type CrackingJob } from '../api/cracking'

interface DashboardData {
  engagements: Engagement[]
  summary: FindingSummary | null
  crackingJobs: CrackingJob[]
}

const ICONS = {
  engagement: 'M7 3h7l5 5v13H7V3zm7 0v6h5M10 14h6m-6 3h4',
  risk: 'M12 3l9 16H3L12 3zm0 6v4m0 3h.01',
  finding: 'M5 12l4 4L19 6',
  jobs: 'M13 2L4 14h7l-1 8 9-13h-7l1-7z',
}

function MetricIcon({ path }: { path: string }) {
  return <div className="metric-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d={path} /></svg></div>
}

export function Dashboard() {
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [engagements, crackingJobs] = await Promise.all([
          engagementsApi.list(),
          crackingApi.jobs().catch(() => []),
        ])
        const activeEngagement = engagements.find((engagement) => engagement.status === 'ACTIVE')
        const summary = activeEngagement
          ? await findingsApi.summary(activeEngagement.id).catch(() => null)
          : null
        setData({ engagements, summary, crackingJobs })
      } catch (requestError: any) {
        setError(requestError.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <LoadingSpinner text="Preparando el centro de operaciones..." />
  if (error) return <div className="callout callout-error">No pudimos cargar el workspace: {error}</div>

  const activeEngagements = data?.engagements.filter((engagement) => engagement.status === 'ACTIVE') ?? []
  const criticalOpen = data?.summary?.open_critical ?? 0
  const highOpen = data?.summary?.open_high ?? 0
  const activeJobs = data?.crackingJobs.filter((job) => job.status === 'RUNNING' || job.status === 'QUEUED') ?? []

  return (
    <div className="page-container dashboard-page">
      <div className="page-heading dashboard-heading">
        <div>
          <span className="eyebrow">Centro de operaciones</span>
          <h1>Panorama de seguridad</h1>
          <p>Prioridades y actividad de todos tus engagements en una única vista.</p>
        </div>
        <div className="page-actions">
          <Link to="/discovery" className="btn btn-secondary">Iniciar discovery</Link>
          <Link to="/engagements/new" className="btn btn-primary">
            <span aria-hidden="true">＋</span> Nuevo engagement
          </Link>
        </div>
      </div>

      <section className="metrics-grid" aria-label="Indicadores principales">
        <article className="metric-card metric-accent">
          <div className="metric-top"><span className="metric-label">Engagements</span><MetricIcon path={ICONS.engagement} /></div>
          <div className="metric-value">{data?.engagements.length ?? 0}</div>
          <div className="metric-foot"><span className="metric-indicator" />{activeEngagements.length} activos ahora</div>
        </article>
        <article className="metric-card metric-danger">
          <div className="metric-top"><span className="metric-label">Riesgo crítico</span><MetricIcon path={ICONS.risk} /></div>
          <div className="metric-value">{criticalOpen}</div>
          <div className="metric-foot">{highOpen} hallazgos de severidad alta</div>
        </article>
        <article className="metric-card metric-warning">
          <div className="metric-top"><span className="metric-label">Hallazgos</span><MetricIcon path={ICONS.finding} /></div>
          <div className="metric-value">{data?.summary?.total ?? 0}</div>
          <div className="metric-foot">Registrados en la auditoría activa</div>
        </article>
        <article className="metric-card metric-purple">
          <div className="metric-top"><span className="metric-label">Trabajos activos</span><MetricIcon path={ICONS.jobs} /></div>
          <div className="metric-value">{activeJobs.length}</div>
          <div className="metric-foot">{data?.crackingJobs.length ?? 0} ejecutados en total</div>
        </article>
      </section>

      {data?.engagements.length === 0 && (
        <section className="onboarding-panel">
          <div className="onboarding-copy">
            <span className="eyebrow">Primeros pasos</span>
            <h2>Configura tu primer workspace de auditoría</h2>
            <p>Crea el engagement, define el alcance autorizado y valida el entorno antes de iniciar actividad inalámbrica.</p>
            <div className="page-actions"><Link to="/engagements/new" className="btn btn-primary">Crear engagement</Link><Link to="/tools" className="btn btn-secondary">Verificar entorno</Link></div>
          </div>
          <ol className="onboarding-steps">
            <li><span>01</span><div><strong>Alcance</strong><small>Objetivos y activos autorizados</small></div></li>
            <li><span>02</span><div><strong>Reconocimiento</strong><small>APs, clientes y superficie</small></div></li>
            <li><span>03</span><div><strong>Validación</strong><small>Evidencia y resultados</small></div></li>
          </ol>
        </section>
      )}

      <div className="dashboard-grid">
        <section className="card dashboard-table-card">
          <div className="card-header">
            <div><div className="card-kicker">Workspace</div><h2 className="card-title">Engagements activos</h2><div className="card-subtitle">Auditorías actualmente en ejecución</div></div>
            <Link to="/engagements" className="text-link">Ver todos <span>→</span></Link>
          </div>
          {activeEngagements.length === 0 ? (
            <div className="compact-empty"><div className="empty-orbit" /><strong>Sin engagements activos</strong><span>Inicia uno para ver aquí su estado.</span><Link to="/engagements/new">Crear engagement</Link></div>
          ) : (
            <div className="table-container"><table><thead><tr><th>Código</th><th>Cliente</th><th>Estado</th></tr></thead><tbody>
              {activeEngagements.map((engagement) => (
                <tr key={engagement.id} className="clickable" onClick={() => navigate(`/engagements/${engagement.id}`)}>
                  <td><Link to={`/engagements/${engagement.id}`} className="primary-cell">{engagement.code}</Link></td><td>{engagement.client}</td><td><StatusBadge status={engagement.status} /></td>
                </tr>
              ))}
            </tbody></table></div>
          )}
        </section>

        <section className="card dashboard-table-card">
          <div className="card-header">
            <div><div className="card-kicker">Procesamiento</div><h2 className="card-title">Últimos trabajos</h2><div className="card-subtitle">Actividad de análisis de credenciales</div></div>
            <Link to="/cracking" className="text-link">Ver todos <span>→</span></Link>
          </div>
          {!data?.crackingJobs.length ? (
            <div className="compact-empty"><div className="empty-orbit" /><strong>Sin trabajos recientes</strong><span>La actividad aparecerá aquí.</span></div>
          ) : (
            <div className="table-container"><table><thead><tr><th>Trabajo</th><th>Estrategia</th><th>Estado</th><th>Progreso</th></tr></thead><tbody>
              {data.crackingJobs.slice(0, 5).map((job) => (
                <tr key={job.id} className="clickable" onClick={() => navigate(`/cracking/${job.id}`)}>
                  <td><Link to={`/cracking/${job.id}`} className="primary-cell">#{job.id}</Link></td><td>{job.strategy}</td><td><StatusBadge status={job.status} /></td><td><div className="progress-cell"><div className="progress-track"><span style={{ width: `${Math.min(100, (job.progress ?? 0) * 100)}%` }} /></div><small>{job.progress != null ? `${(job.progress * 100).toFixed(0)}%` : '—'}</small></div></td>
                </tr>
              ))}
            </tbody></table></div>
          )}
        </section>
      </div>
    </div>
  )
}
