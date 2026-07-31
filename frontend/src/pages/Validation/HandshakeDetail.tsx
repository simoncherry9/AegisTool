import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { StatusBadge } from '../../components/StatusBadge'
import { validationApi, type HandshakeReport } from '../../api/validation'
import { crackingApi, type HashInfo } from '../../api/cracking'
import { engagementsApi, type Engagement } from '../../api/engagements'

export function HandshakeDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [artifact, setArtifact] = useState<HandshakeReport | null>(null)
  const [hashInfo, setHashInfo] = useState<HashInfo | null>(null)
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [selectedEng, setSelectedEng] = useState<number | undefined>()
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [art, engs] = await Promise.all([
          validationApi.artifact(Number(id)),
          engagementsApi.list().catch(() => []),
        ])
        setArtifact(art)
        setEngagements(engs)
        const active = engs.find(e => e.status === 'ACTIVE')
        if (active) setSelectedEng(active.id)

        // Intentar obtener hash info si está validado
        if (art.validated) {
          crackingApi.hashInfo(Number(id)).then(setHashInfo).catch(() => {})
        }
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  async function handleCreateJob() {
    if (!selectedEng) {
      setError('Selecciona un engagement')
      return
    }
    setCreating(true)
    setError(null)
    try {
      const job = await crackingApi.createJob(Number(id), 'dictionary', selectedEng)
      navigate('/cracking/' + job.id)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setCreating(false)
    }
  }

  async function handleReprocess() {
    try {
      await validationApi.reprocess(Number(id))
      const updated = await validationApi.artifact(Number(id))
      setArtifact(updated)
    } catch (e: any) {
      setError(e.message)
    }
  }

  function qualityColor(q: string): string {
    const map: Record<string, string> = {
      EXCELLENT: 'var(--green)', GOOD: 'var(--green)',
      ACCEPTABLE: 'var(--yellow)', POOR: 'var(--orange)',
      INVALID: 'var(--red)',
    }
    return map[q] || 'var(--text-muted)'
  }

  if (loading) return <LoadingSpinner text="Cargando handshake..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>
  if (!artifact) return <div className="callout callout-warning">Handshake no encontrado</div>

  return (
    <div>
      <div className="detail-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1>Handshake #{artifact.id}</h1>
            <span style={{ color: qualityColor(artifact.quality), fontWeight: 700 }}>{artifact.quality}</span>
            {artifact.validated ?
              <span className="badge badge-active">Validado</span> :
              <span className="badge badge-closed">No validado</span>
            }
          </div>
          <div className="subtitle">
            {artifact.ssid || '—'} {artifact.bssid ? '(' + artifact.bssid + ')' : ''}
            {artifact.created_at ? ' — ' + new Date(artifact.created_at).toLocaleString() : ''}
          </div>
        </div>
        <div className="detail-actions">
          <button className="btn btn-secondary" onClick={handleReprocess}>↻ Reprocesar</button>
          <button className="btn btn-primary" disabled={!artifact.validated || creating} onClick={handleCreateJob}>
            {creating ? 'Creando...' : '⚡ Crear job de cracking'}
          </button>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header"><div className="card-title">Información</div></div>
          <div className="detail-grid">
            <div className="detail-field">
              <div className="detail-label">SSID</div>
              <div className="detail-value">{artifact.ssid || '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">BSSID</div>
              <div className="detail-value" style={{ fontFamily: 'monospace' }}>{artifact.bssid || '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Canal</div>
              <div className="detail-value">{artifact.channel ?? '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Tipo</div>
              <div className="detail-value">{artifact.kind}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Pares de mensajes</div>
              <div className="detail-value">{artifact.message_pair || '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Cracking</div>
              <div className="detail-value">{artifact.crack_status ? <StatusBadge status={artifact.crack_status} /> : '—'}</div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title">Hash file</div></div>
          <div className="detail-grid">
            <div className="detail-field" style={{ gridColumn: '1 / -1' }}>
              <div className="detail-label">Archivo .22000</div>
              <div className="detail-value" style={{ fontSize: 11, fontFamily: 'monospace', wordBreak: 'break-all' }}>
                {artifact.hash_file || '—'}
              </div>
            </div>
            {hashInfo && (
              <>
                <div className="detail-field" style={{ gridColumn: '1 / -1' }}>
                  <div className="detail-label">Hash line</div>
                  <div className="detail-value" style={{ fontSize: 10, fontFamily: 'monospace', wordBreak: 'break-all' }}>
                    {hashInfo.hash_line}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {artifact.validated && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div className="card-title">Crear job de cracking</div>
          </div>
          <div style={{ padding: '0 20px 20px', display: 'flex', gap: 12, alignItems: 'flex-end' }}>
            <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
              <label className="form-label">Engagement</label>
              <select className="form-select" value={selectedEng ?? ''} onChange={e => setSelectedEng(Number(e.target.value) || undefined)}>
                <option value="">Seleccionar</option>
                {engagements.map(e => (
                  <option key={e.id} value={e.id}>{e.code}</option>
                ))}
              </select>
            </div>
            <button className="btn btn-primary" onClick={handleCreateJob} disabled={creating}>
              {creating ? 'Creando...' : '⚡ Crear job'}
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/cracking/analyze/' + artifact.id)}>
              Ver plan
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
