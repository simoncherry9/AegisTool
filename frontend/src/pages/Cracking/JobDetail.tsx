import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { StatusBadge } from '../../components/StatusBadge'
import { crackingApi, type CrackingJob } from '../../api/cracking'

export function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const [job, setJob] = useState<CrackingJob | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    crackingApi.job(Number(id))
      .then(setJob)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  async function handleCancel() {
    if (!job) return
    setCancelling(true)
    try {
      await crackingApi.cancelJob(job.id)
      const updated = await crackingApi.job(job.id)
      setJob(updated)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setCancelling(false)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando trabajo..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>
  if (!job) return <div className="callout callout-warning">Trabajo no encontrado</div>

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Cracking #{job.id}</h1>
          <div className="subtitle">{job.strategy}</div>
        </div>
        <div className="detail-actions">
          {(job.status === 'CREATED' || job.status === 'QUEUED' || job.status === 'RUNNING') && (
            <button className="btn btn-danger" disabled={cancelling} onClick={handleCancel}>
              {cancelling ? 'Cancelando...' : 'Cancelar'}
            </button>
          )}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="detail-grid">
          <div className="detail-field">
            <div className="detail-label">Estado</div>
            <div className="detail-value"><StatusBadge status={job.status} /></div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Progreso</div>
            <div className="detail-value">{job.progress != null ? `${(job.progress * 100).toFixed(1)}%` : '—'}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Velocidad</div>
            <div className="detail-value">{job.speed ? `${(job.speed / 1000).toFixed(0)}k H/s` : '—'}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Contraseña recuperada</div>
            <div className="detail-value">{job.recovered ? <span style={{ color: 'var(--green)', fontWeight: 600 }}>SÍ</span> : 'No'}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Keyspace</div>
            <div className="detail-value">{job.keyspace?.toLocaleString() ?? '—'}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Inicio</div>
            <div className="detail-value">{job.started_at ? new Date(job.started_at).toLocaleString() : '—'}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Fin</div>
            <div className="detail-value">{job.finished_at ? new Date(job.finished_at).toLocaleString() : '—'}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
