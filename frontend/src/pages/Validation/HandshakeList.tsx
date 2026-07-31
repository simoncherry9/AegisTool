import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { StatusBadge } from '../../components/StatusBadge'
import { validationApi, type HandshakeReport } from '../../api/validation'

export function HandshakeList() {
  const [artifacts, setArtifacts] = useState<HandshakeReport[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [qualityFilter, setQualityFilter] = useState('')
  const [validatedOnly, setValidatedOnly] = useState(false)

  useEffect(() => {
    validationApi.artifacts({ quality: qualityFilter || undefined })
      .then(setArtifacts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [qualityFilter])

  if (loading) return <LoadingSpinner text="Cargando handshakes..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>

  const filtered = validatedOnly ? artifacts.filter((a) => a.validated) : artifacts

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Handshakes</h1>
          <div className="subtitle">Handshakes EAPOL/PMKID validados</div>
        </div>
      </div>

      <div className="filters">
        <select className="form-select" value={qualityFilter} onChange={(e) => setQualityFilter(e.target.value)}>
          <option value="">Todas las calidades</option>
          <option value="EXCELLENT">EXCELLENT</option>
          <option value="GOOD">GOOD</option>
          <option value="ACCEPTABLE">ACCEPTABLE</option>
          <option value="POOR">POOR</option>
          <option value="INVALID">INVALID</option>
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
          <input type="checkbox" checked={validatedOnly} onChange={(e) => setValidatedOnly(e.target.checked)} />
          Solo validados
        </label>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="Sin handshakes"
          description="Valida una captura desde la API o CLI para ver handshakes aquí."
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>#</th><th>SSID</th><th>BSSID</th><th>Tipo</th><th>Calidad</th><th>Validado</th><th>Pares</th><th>Cracking</th></tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <tr key={a.id}>
                    <td><Link to={`/handshakes/${a.id}`} style={{ fontWeight: 600 }}>#{a.id}</Link></td>
                    <td style={{ fontWeight: 500 }}>{a.ssid || '—'}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{a.bssid || '—'}</td>
                    <td style={{ fontSize: 12 }}>{a.kind}</td>
                    <td><StatusBadge status={a.quality} /></td>
                    <td>{a.validated ? <span className="badge badge-validated">✓</span> : <span className="badge badge-unvalidated">✗</span>}</td>
                    <td style={{ fontSize: 12 }}>{a.message_pair || '—'}</td>
                    <td>{a.crack_status ? <StatusBadge status={a.crack_status} /> : '—'}</td>
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
