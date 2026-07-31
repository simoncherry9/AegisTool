import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { validationApi, type HandshakeReport } from '../../api/validation'

export function ValidationPage() {
  const [artifacts, setArtifacts] = useState<HandshakeReport[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [qualityFilter, setQualityFilter] = useState('')
  const [validatedOnly, setValidatedOnly] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validateResult, setValidateResult] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    validationApi.artifacts({ quality: qualityFilter || undefined })
      .then(setArtifacts)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [qualityFilter])

  const filtered = validatedOnly ? artifacts.filter(a => a.validated) : artifacts

  async function handleReprocess(id: number) {
    if (!confirm('Reprocesar artifact #' + id + '?')) return
    try {
      const res = await validationApi.reprocess(id)
      setValidateResult('Artifact #' + id + ' reprocesado: ' + res.result.quality + ' (' + (res.result.validated ? 'válido' : 'inválido') + ')')
      // Recargar
      const updated = await validationApi.artifacts({ quality: qualityFilter || undefined })
      setArtifacts(updated)
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

  if (loading) return <LoadingSpinner text="Cargando handshakes..." />

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Validación de handshakes</h1>
          <div className="subtitle">EAPOL / PMKID — calidad y parámetros</div>
        </div>
        <div className="detail-actions">
          <button className="btn btn-primary" onClick={() => navigate('/validation/validate')}>+ Validar captura</button>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}
      {validateResult && (
        <div className="callout" style={{ borderLeft: '3px solid var(--green)' }}>
          {validateResult}
          <button style={{ marginLeft: 12, cursor: 'pointer', background: 'none', border: 'none', color: 'var(--text-muted)' }}
            onClick={() => setValidateResult(null)}>✕</button>
        </div>
      )}

      <div className="filters">
        <select className="form-select" value={qualityFilter} onChange={e => setQualityFilter(e.target.value)}>
          <option value="">Todas las calidades</option>
          <option value="EXCELLENT">EXCELLENT</option>
          <option value="GOOD">GOOD</option>
          <option value="ACCEPTABLE">ACCEPTABLE</option>
          <option value="POOR">POOR</option>
          <option value="INVALID">INVALID</option>
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
          <input type="checkbox" checked={validatedOnly} onChange={e => setValidatedOnly(e.target.checked)} />
          Solo validados
        </label>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="Sin handshakes"
          description="Valida una captura para ver handshakes aquí."
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>#</th><th>SSID</th><th>BSSID</th><th>Tipo</th><th>Calidad</th><th>Val.</th><th>Pares</th><th>Cracking</th><th>Acción</th></tr>
              </thead>
              <tbody>
                {filtered.map(a => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 600 }}><a href={'/handshakes/' + a.id}>#{a.id}</a></td>
                    <td style={{ fontWeight: 500, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.ssid || '—'}
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{a.bssid || '—'}</td>
                    <td style={{ fontSize: 12 }}>{a.kind}</td>
                    <td><span style={{ color: qualityColor(a.quality), fontWeight: 600, fontSize: 12 }}>{a.quality}</span></td>
                    <td>{a.validated ? <span style={{ color: 'var(--green)' }}>✓</span> : <span style={{ color: 'var(--red)' }}>✗</span>}</td>
                    <td style={{ fontSize: 12 }}>{a.message_pair || '—'}</td>
                    <td>{a.crack_status ? <span className="badge">{a.crack_status}</span> : '—'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button className="btn btn-sm btn-secondary"
                          style={{ fontSize: 10, padding: '2px 8px' }}
                          onClick={() => handleReprocess(a.id)}>↻</button>
                        {a.validated && (
                          <button className="btn btn-sm btn-primary"
                            style={{ fontSize: 10, padding: '2px 8px' }}
                            onClick={() => navigate('/cracking/analyze/' + a.id)}>⚡</button>
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
