import { useState, useEffect } from 'react'
import { wpsApi } from '../../api/wps'
import { discoveryApi, type AccessPoint } from '../../api/discovery'
import { LoadingSpinner } from '../../components/LoadingSpinner'

export function WPSPage() {
  const [wpsAps, setWpsAps] = useState<AccessPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeAttacks, setActiveAttacks] = useState<any[]>([])

  const loadData = async () => {
    try {
      const aps = await discoveryApi.accessPoints({ wps: true, limit: 100 })
      setWpsAps(aps as AccessPoint[])
      const attacks = (await wpsApi.attacks().catch(() => [])) as any[]
      setActiveAttacks(attacks)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(() => {
      wpsApi.attacks().then(attacks => setActiveAttacks(attacks as any[])).catch(() => {})
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleScan = async () => {
    setScanning(true)
    setError(null)
    try {
      await wpsApi.scan()
      await new Promise(r => setTimeout(r, 2000))
      await loadData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setScanning(false)
    }
  }

  const handleAttack = async (bssid: string, type: string) => {
    try {
      await wpsApi.attack({ bssid, type })
      loadData()
    } catch (err: any) {
      setError(err.message)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando datos WPS..." />

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Auditoría WPS</h1>
          <div className="subtitle">Escaneo y ataque de redes con WPS habilitado</div>
        </div>
        <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
          {scanning ? 'Escaneando...' : '🔍 Escanear WPS'}
        </button>
      </div>

      {error && <div className="callout callout-error">{error}</div>}

      <div className="card" style={{ padding: 0, marginBottom: 24 }}>
        <div className="card-header" style={{ padding: '22px 22px 0' }}>
          <div className="card-title">Puntos de Acceso Vulnerables</div>
        </div>
        {wpsAps.length === 0 ? (
          <div className="empty-state">
            <p>No se han detectado redes con WPS habilitado.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>SSID</th>
                  <th>BSSID</th>
                  <th>Señal</th>
                  <th>Acciones de Ataque</th>
                </tr>
              </thead>
              <tbody>
                {wpsAps.map(ap => (
                  <tr key={ap.bssid}>
                    <td style={{ fontWeight: 600 }}>{ap.ssid || '<Oculto>'}</td>
                    <td style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>{ap.bssid}</td>
                    <td>{ap.signal} dBm</td>
                    <td>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn btn-sm btn-secondary" onClick={() => handleAttack(ap.bssid, 'pixie-dust')}>Pixie-Dust</button>
                        <button className="btn btn-sm btn-secondary" onClick={() => handleAttack(ap.bssid, 'brute-force')}>Brute Force</button>
                        <button className="btn btn-sm btn-secondary" onClick={() => handleAttack(ap.bssid, 'bully')}>Bully</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Ataques Activos</div>
        </div>
        {activeAttacks.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No hay ataques en curso.</div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>BSSID</th>
                  <th>Tipo</th>
                  <th>Estado</th>
                  <th>Progreso</th>
                </tr>
              </thead>
              <tbody>
                {activeAttacks.map(attack => (
                  <tr key={attack.id}>
                    <td style={{ fontFamily: 'monospace' }}>{attack.bssid}</td>
                    <td>{attack.type}</td>
                    <td>
                      <span className="badge badge-active" style={{ animation: 'pulse 2s infinite' }}>{attack.status}</span>
                    </td>
                    <td>{attack.progress || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
