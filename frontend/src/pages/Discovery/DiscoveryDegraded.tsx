import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { discoveryApi, type AccessPoint } from '../../api/discovery'

export function DiscoveryDegraded() {
  const [aps, setAps] = useState<AccessPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    discoveryApi.degraded()
      .then(setAps)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner text="Cargando APs degradados..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>APs con seguridad degradada</h1>
          <div className="subtitle">Puntos de acceso con configuraciones inseguras</div>
        </div>
        <div className="detail-actions">
          <button className="btn btn-sm btn-secondary" onClick={() => window.location.reload()}>↻ Recargar</button>
        </div>
      </div>

      {aps.length === 0 ? (
        <EmptyState
          title="Sin APs degradados"
          description="Todos los puntos de acceso detectados tienen configuraciones de seguridad adecuadas."
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>SSID</th><th>BSSID</th><th>Protocolo</th><th>AKM</th><th>WPS</th><th>PMF</th><th>Señal</th><th>Clientes</th></tr>
              </thead>
              <tbody>
                {aps.map((ap, i) => (
                  <tr key={ap.bssid + '-' + i} className="clickable" onClick={() => navigate('/discovery/ap/' + ap.bssid)}>
                    <td style={{ fontWeight: 500 }}>{ap.ssid || '<Oculto>'}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{ap.bssid}</td>
                    <td><span className="badge">{ap.protocol}</span></td>
                    <td style={{ fontSize: 11, fontFamily: 'monospace' }}>{ap.akm || '—'}</td>
                    <td>{ap.wps ? <span style={{ color: 'var(--red)' }}>✓</span> : '—'}</td>
                    <td style={{ fontSize: 11 }}>{ap.pmf !== 'unknown' ? ap.pmf : '—'}</td>
                    <td>{ap.signal != null ? ap.signal + ' dBm' : '—'}</td>
                    <td>{ap.clients_count || '—'}</td>
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
