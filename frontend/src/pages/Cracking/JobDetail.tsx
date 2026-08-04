import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { StatusBadge } from '../../components/StatusBadge'
import { crackingApi, type CrackingJob, type DictionaryInfo } from '../../api/cracking'
import { engagementsApi, type Engagement } from '../../api/engagements'

export function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const [job, setJob] = useState<CrackingJob | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const [starting, setStarting] = useState(false)
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [engagementId, setEngagementId] = useState<number | undefined>()
  const [dictionaries, setDictionaries] = useState<DictionaryInfo[]>([])
  const [dictionaryPath, setDictionaryPath] = useState('')

  useEffect(() => {
    Promise.all([
      crackingApi.job(Number(id)),
      engagementsApi.list(),
      crackingApi.dictionaries(),
    ])
      .then(([loadedJob, loadedEngagements, loadedDictionaries]) => {
        setJob(loadedJob)
        setEngagements(loadedEngagements)
        setEngagementId(loadedEngagements.find(item => item.status === 'ACTIVE')?.id)
        const usable = loadedDictionaries.filter(item => !item.compressed)
        setDictionaries(usable)
        setDictionaryPath(usable.find(item => item.name.toLowerCase().includes('rockyou'))?.path ?? usable[0]?.path ?? '')
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!job || !['QUEUED', 'VALIDATING', 'RUNNING', 'RESTORING'].includes(job.status)) return
    const timer = window.setInterval(() => {
      crackingApi.job(job.id).then(setJob).catch(e => setError(e.message))
    }, 1500)
    return () => window.clearInterval(timer)
  }, [job?.id, job?.status])

  async function handleStart() {
    if (!job || !engagementId || !dictionaryPath) {
      setError('Selecciona un engagement activo y un diccionario descomprimido')
      return
    }
    setStarting(true)
    setError(null)
    try {
      await crackingApi.startJob(job.id, engagementId, [dictionaryPath])
      setJob(await crackingApi.job(job.id))
    } catch (e: any) {
      setError(e.message)
    } finally {
      setStarting(false)
    }
  }

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
          {job.status === 'CREATED' && (
            <button className="btn btn-primary" disabled={starting} onClick={handleStart}>
              {starting ? 'Iniciando...' : 'Iniciar Hashcat'}
            </button>
          )}
          {(job.status === 'CREATED' || job.status === 'QUEUED' || job.status === 'RUNNING') && (
            <button className="btn btn-danger" disabled={cancelling} onClick={handleCancel}>
              {cancelling ? 'Cancelando...' : 'Cancelar'}
            </button>
          )}
        </div>
      </div>

      {job.status === 'CREATED' && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header"><div className="card-title">Configuración de inicio</div></div>
          <div className="grid grid-2">
            <div className="form-group">
              <label className="form-label">Engagement activo</label>
              <select className="form-select" value={engagementId ?? ''} onChange={event => setEngagementId(Number(event.target.value) || undefined)}>
                <option value="">Seleccionar</option>
                {engagements.filter(item => item.status === 'ACTIVE').map(item => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Diccionario</label>
              <select className="form-select" value={dictionaryPath} onChange={event => setDictionaryPath(event.target.value)}>
                <option value="">Seleccionar</option>
                {dictionaries.map(item => <option key={item.path} value={item.path}>{item.name}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}

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
