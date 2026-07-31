import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { StatusBadge } from '../../components/StatusBadge'
import { jobsApi, type JobDetail, type JobEvent } from '../../api/jobs'

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [job, setJob] = useState<JobDetail | null>(null)
  const [events, setEvents] = useState<JobEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [j, evts] = await Promise.all([
          jobsApi.get(Number(id)),
          jobsApi.events(Number(id)).catch(() => []),
        ])
        setJob(j)
        setEvents(evts)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  async function handleCancel() {
    if (!confirm('Cancelar trabajo #' + id + '?')) return
    try {
      const updated = await jobsApi.cancel(Number(id))
      setJob(updated)
    } catch (e: any) {
      setError(e.message)
    }
  }

  async function handleRetry() {
    try {
      const updated = await jobsApi.retry(Number(id))
      setJob(updated)
    } catch (e: any) {
      setError(e.message)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando trabajo..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>
  if (!job) return <div className="callout callout-warning">Trabajo no encontrado</div>

  const isActive = job.status === 'QUEUED' || job.status === 'RUNNING'
  const isFailed = job.status === 'FAILED'

  return (
    <div>
      <div className="detail-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1>Trabajo #{job.id}</h1>
            <StatusBadge status={job.status} />
            <span className="badge">{job.kind}</span>
          </div>
          <div className="subtitle">
            Engagement <a href={'/engagements/' + job.engagement_id}>#{job.engagement_id}</a>
            {job.created_at ? ' — Creado ' + new Date(job.created_at).toLocaleString() : ''}
          </div>
        </div>
        <div className="detail-actions">
          {isActive && <button className="btn btn-danger" onClick={handleCancel}>Cancelar</button>}
          {isFailed && <button className="btn btn-secondary" onClick={handleRetry}>Reintentar</button>}
        </div>
      </div>

      {job.message && <div className="callout">{job.message}</div>}
      {job.error && <div className="callout callout-error">Error: {job.error}</div>}

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header"><div className="card-title">Progreso</div></div>
          {job.progress != null ? (
            <div style={{ padding: '0 20px 20px' }}>
              <div className="progress-bar" style={{ height: 24, background: 'var(--bg-secondary)', borderRadius: 12, overflow: 'hidden' }}>
                <div style={{
                  width: (job.progress * 100) + '%', height: '100%',
                  background: 'var(--accent)', borderRadius: 12,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 600, color: '#fff',
                  minWidth: job.progress > 0.05 ? undefined : 0,
                }}>
                  {(job.progress * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: '0 20px 20px', color: 'var(--text-muted)', fontSize: 13 }}>Sin progreso</div>
          )}
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">Detalles</div></div>
          <div className="detail-grid" style={{ padding: '0 20px 20px' }}>
            <div className="detail-field">
              <div className="detail-label">Estado</div>
              <div className="detail-value"><StatusBadge status={job.status} /></div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Iniciado</div>
              <div className="detail-value">{job.started_at ? new Date(job.started_at).toLocaleString() : '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Finalizado</div>
              <div className="detail-value">{job.finished_at ? new Date(job.finished_at).toLocaleString() : '—'}</div>
            </div>
          </div>
        </div>
      </div>

      {events.length > 0 && (
        <div className="card">
          <div className="card-header"><div className="card-title">Eventos ({events.length})</div></div>
          <div className="table-container">
            <table>
              <thead><tr><th>Tipo</th><th>Mensaje</th><th>Timestamp</th></tr></thead>
              <tbody>
                {events.map((ev, i) => (
                  <tr key={ev.id || i}>
                    <td><span className="badge">{ev.event_type}</span></td>
                    <td style={{ fontSize: 13 }}>{ev.message || '—'}</td>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {job.result && Object.keys(job.result).length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header"><div className="card-title">Resultado</div></div>
          <pre style={{ padding: 16, fontSize: 12, overflow: 'auto', maxHeight: 300 }}>
            {JSON.stringify(job.result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
