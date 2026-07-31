import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { validationApi } from '../../api/validation'
import { engagementsApi, type Engagement } from '../../api/engagements'
import { useEffect } from 'react'

export function ValidateCapture() {
  const navigate = useNavigate()
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [engagementId, setEngagementId] = useState<number | undefined>()
  const [filePath, setFilePath] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    engagementsApi.list().then(setEngagements).catch(() => {})
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!filePath.trim()) {
      setError('La ruta del archivo es obligatoria')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const res = await validationApi.validate({
        file_path: filePath.trim(),
        engagement_id: engagementId || null,
      })
      setResult('Artifact #' + res.result.artifact_id + ' creado — Calidad: ' + res.result.quality)
    } catch (e: any) {
      setError(e.message || 'Error al validar')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 560 }}>
      <div className="detail-header">
        <div>
          <h1>Validar captura</h1>
          <div className="subtitle">Analizar un archivo .pcapng en busca de handshakes</div>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}
      {result && (
        <div className="callout" style={{ borderLeft: '3px solid var(--green)' }}>
          {result}
          <div style={{ marginTop: 8 }}>
            <button className="btn btn-sm btn-primary" onClick={() => navigate('/validation')}>Ver artifacts</button>
          </div>
        </div>
      )}

      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Ruta del archivo .pcapng</label>
            <input className="form-input" value={filePath} onChange={e => setFilePath(e.target.value)}
              placeholder="/home/user/captura.pcapng" required />
          </div>
          <div className="form-group">
            <label className="form-label">Engagement (opcional)</label>
            <select className="form-select" value={engagementId ?? ''} onChange={e => setEngagementId(Number(e.target.value) || undefined)}>
              <option value="">Sin asociar</option>
              {engagements.map(e => (
                <option key={e.id} value={e.id}>{e.code} — {e.name}</option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 24 }}>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Validando...' : 'Validar captura'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/validation')}>Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  )
}
