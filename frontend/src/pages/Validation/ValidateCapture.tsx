import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { validationApi, type ValidationResult } from '../../api/validation'
import { engagementsApi, type Engagement } from '../../api/engagements'
import { useEffect } from 'react'

export function ValidateCapture() {
  const navigate = useNavigate()
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [engagementId, setEngagementId] = useState<number | undefined>()
  const [filePath, setFilePath] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ValidationResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    engagementsApi.list()
      .then(data => {
        setEngagements(data)
        const preferred = data.find(engagement => engagement.status === 'ACTIVE') || data[0]
        setEngagementId(preferred?.id)
      })
      .catch(() => {})
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!filePath.trim()) {
      setError('La ruta del archivo es obligatoria')
      return
    }
    if (!engagementId) {
      setError('Selecciona un engagement para registrar la evidencia')
      return
    }
    setSubmitting(true)
    setError(null)
    setResult(null)
    try {
      const res = await validationApi.validate({
        file_path: filePath.trim(),
        engagement_id: engagementId,
      })
      setResult(res.result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al validar')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 560 }}>
      <div className="detail-header">
        <div>
          <h1>Validar captura</h1>
          <div className="subtitle">Analizar archivos .cap, .pcap o .pcapng en busca de EAPOL y PMKID</div>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}
      {result && (
        <div className={`callout ${result.validated ? 'callout-success' : 'callout-error'}`}>
          <strong>{result.validated ? 'Captura utilizable' : 'Captura no utilizable'}</strong>
          <div style={{ marginTop: 4 }}>
            Calidad: {result.quality} · Puntaje: {Math.round(result.quality_score * 100)}%
            {result.artifact_id ? ` · Artifact #${result.artifact_id}` : ''}
          </div>
          {result.message_pair && <div style={{ marginTop: 4 }}>Message pair: {result.message_pair}</div>}
          {result.warnings?.map((warning, index) => (
            <div key={`warning-${index}`} style={{ marginTop: 6 }}>Advertencia: {warning}</div>
          ))}
          {result.errors.map((validationError, index) => (
            <div key={`error-${index}`} style={{ marginTop: 6 }}>{validationError}</div>
          ))}
          <div style={{ marginTop: 8 }}>
            <button className="btn btn-sm btn-primary" onClick={() => navigate('/validation')}>Ver artifacts</button>
          </div>
        </div>
      )}

      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Ruta del archivo de captura</label>
            <input className="form-input" value={filePath} onChange={e => setFilePath(e.target.value)}
              placeholder="/home/user/captura.cap" required />
          </div>
          <div className="form-group">
            <label className="form-label">Engagement</label>
            <select className="form-select" value={engagementId ?? ''} onChange={e => setEngagementId(Number(e.target.value) || undefined)}>
              <option value="" disabled>Seleccionar engagement</option>
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
