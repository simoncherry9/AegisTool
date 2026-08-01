import { useState, useEffect } from 'react'
import { deauthApi } from '../../api/deauth'
import { discoveryApi, type AccessPoint, type ClientSummary } from '../../api/discovery'

export function DeauthPage() {
  const [aps, setAps] = useState<AccessPoint[]>([])
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [history, setHistory] = useState<any[]>([])
  
  const [bssid, setBssid] = useState('')
  const [clientMac, setClientMac] = useState('')
  const [count, setCount] = useState(10)
  const [status, setStatus] = useState<{ type: 'success'|'error', msg: string } | null>(null)

  useEffect(() => {
    discoveryApi.accessPoints({ limit: 200 }).then(res => setAps(res as AccessPoint[])).catch(() => {})
    discoveryApi.clients().then(res => setClients(res as ClientSummary[])).catch(() => {})
    deauthApi.history().then(res => setHistory(res as any[])).catch(() => {})
  }, [])

  const filteredClients = bssid ? clients.filter(c => c.associated_bssid === bssid) : clients

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus(null)
    try {
      const ap = aps.find(a => a.bssid === bssid)
      await deauthApi.send({
        bssid,
        client_mac: clientMac || undefined,
        count,
        channel: ap?.channel
      })
      setStatus({ type: 'success', msg: 'Ataque deauth enviado exitosamente.' })
      deauthApi.history().then(res => setHistory(res as any[])).catch(() => {})
    } catch (err: any) {
      setStatus({ type: 'error', msg: err.message || 'Error al enviar deauth.' })
    }
  }

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Deauthentication</h1>
          <div className="subtitle">Desconexión forzada de clientes (Deauth Attack)</div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">Lanzar Ataque</div>
          </div>
          {status && (
            <div className={`callout callout-${status.type}`}>
              {status.msg}
            </div>
          )}
          <form onSubmit={handleSend}>
            <div className="form-group">
              <label className="form-label">Access Point (BSSID)</label>
              <select className="form-select" value={bssid} onChange={(e) => { setBssid(e.target.value); setClientMac(''); }} required>
                <option value="">Selecciona un AP...</option>
                {aps.map(ap => (
                  <option key={ap.bssid} value={ap.bssid}>{ap.ssid || '<Oculto>'} ({ap.bssid})</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Cliente (MAC)</label>
              <select className="form-select" value={clientMac} onChange={(e) => setClientMac(e.target.value)}>
                <option value="">Broadcast (Desconectar a todos)</option>
                {filteredClients.map(c => (
                  <option key={c.mac} value={c.mac}>{c.mac} ({c.vendor || 'Desconocido'})</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Cantidad de paquetes ({count})</label>
              <input type="range" min="1" max="100" className="form-input" value={count} onChange={(e) => setCount(Number(e.target.value))} style={{ padding: 0 }} />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%', background: 'linear-gradient(135deg, #ff9100 0%, #ff6d00 100%)' }}>
              ⚡ Ejecutar Ataque Deauth
            </button>
          </form>
        </div>

        <div className="card" style={{ padding: 0 }}>
          <div className="card-header" style={{ padding: '22px 22px 0' }}>
            <div className="card-title">Historial Reciente</div>
          </div>
          {history.length === 0 ? (
            <div className="empty-state">
              <p>No hay historial de ataques.</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>BSSID</th>
                    <th>Cliente</th>
                    <th>Pkts</th>
                    <th>Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 10).map((h, i) => (
                    <tr key={i}>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{h.bssid}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{h.client_mac || 'Broadcast'}</td>
                      <td>{h.count}</td>
                      <td style={{ fontSize: 12 }}>{new Date(h.timestamp).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
