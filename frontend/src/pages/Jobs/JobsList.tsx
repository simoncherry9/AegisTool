import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { StatusBadge } from '../../components/StatusBadge'
import { jobsApi, type JobListItem } from '../../api/jobs'
import { engagementsApi, type Engagement } from '../../api/engagements'

export function JobsList() {
  const [jobs, setJobs] = useState<JobListItem[]>([])
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterEng, setFilterEng] = useState<number | undefined>()
  const [filterKind, setFilterKind] = useState('')
  const [queueStatus, setQueueStatus] = useState<{ queue_size: number; active_workers: number } | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      try {
        const [engs, qs] = await Promise.all([
          engagementsApi.list().catch(() => []),
          jobsApi.queueStatus().catch(() => null),
        ])
        setEngagements(engs)
        setQueueStatus(qs)
      } catch { /* ok */ }
    }
    load()
  }, [])

  useEffect(() => {
    async function loadJobs() {
      setLoading(true)
      try {
        const data = await jobsApi.list({
          engagement_id: filterEng,
          kind: filterKind || undefined,
        })
        setJobs(data)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    loadJobs()
  }, [filterEng, filterKind])

  async function handleCancel(id: number) {
    if (!confirm('Cancelar trabajo #' + id + '?')) return
    try {
      await jobsApi.cancel(id)
      setJobs(jobs.map(j => j.id === id ? { ...j, status: 'CANCELLED' } : j))
    } catch (e: any) {
      setError(e.message)
    }
  }

  const kinds = [...new Set(jobs.map(j => j.kind).filter(Boolean))] as string[]

  if (loading && jobs.length === 0) return <LoadingSpinner text="Cargando trabajos..." />

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Trabajos del sistema</h1>
          <div className="subtitle">Jobs asíncronos y procesos en segundo plano</div>
        </div>
        {queueStatus && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right' }}>
            <div>Cola: {queueStatus.queue_size} | Workers: {queueStatus.active_workers}</div>
          </div>
        )}
      </div>

      {error && <div className="callout callout-error">{error}</div>}

      <div className="filters">
        <select className="form-select" value={filterEng ?? ''} onChange={e => setFilterEng(Number(e.target.value) || undefined)}>
          <option value="">Todos los engagements</option>
          {engagements.map(e => (
            <option key={e.id} value={e.id}>{e.code}</option>
          ))}
        </select>
        <select className="form-select" value={filterKind} onChange={e => setFilterKind(e.target.value)}>
          <option value="">Todos los tipos</option>
          {kinds.map(k => <option key={k} value={k}>{k}</option>)}
        </select>
      </div>

      {jobs.length === 0 ? (
        <EmptyState title="Sin trabajos" description="No hay trabajos registrados en el sistema." />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>#</th><th>Tipo</th><th>Engagement</th><th>Estado</th><th>Progreso</th><th>Creado</th><th>Acción</th></tr>
              </thead>
              <tbody>
                {jobs.map(j => (
                  <tr key={j.id} className="clickable" onClick={() => navigate('/jobs/' + j.id)}>
                    <td style={{ fontWeight: 600 }}>#{j.id}</td>
                    <td><span className="badge">{j.kind}</span></td>
                    <td><a href={'/engagements/' + j.engagement_id} onClick={e => e.stopPropagation()}>#{j.engagement_id}</a></td>
                    <td><StatusBadge status={j.status} /></td>
                    <td>{j.progress != null ? (j.progress * 100).toFixed(0) + '%' : '—'}</td>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{j.created_at ? new Date(j.created_at).toLocaleString() : '—'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {(j.status === 'QUEUED' || j.status === 'RUNNING') && (
                          <button className="btn btn-sm btn-danger" style={{ fontSize: 10, padding: '2px 8px' }}
                            onClick={e => { e.stopPropagation(); handleCancel(j.id) }}>Cancelar</button>
                        )}
                        {j.status === 'FAILED' && (
                          <button className="btn btn-sm btn-secondary" style={{ fontSize: 10, padding: '2px 8px' }}
                            onClick={e => { e.stopPropagation(); jobsApi.retry(j.id).then(() => {
                              setJobs(jobs.map(jj => jj.id === j.id ? { ...jj, status: 'CREATED' } : jj))
                            }) }}>Reintentar</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
