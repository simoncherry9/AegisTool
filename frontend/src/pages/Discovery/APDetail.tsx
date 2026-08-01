import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { discoveryApi, type AccessPoint, type ClientSummary } from '../../api/discovery'
import { handshakeApi } from '../../api/handshake'
import { pmkidApi } from '../../api/pmkid'
import { deauthApi } from '../../api/deauth'
import { wpsApi } from '../../api/wps'
import { api } from '../../api/client'
import { LoadingSpinner } from '../../components/LoadingSpinner'

export function APDetail() {
  const { bssid } = useParams<{ bssid: string }>()
  const navigate = useNavigate()
  
  const [ap, setAp] = useState<AccessPoint | null>(null)
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [inScope, setInScope] = useState<boolean>(false)

  // Forms state
  const [hsDuration, setHsDuration] = useState(60)
  const [hsDeauth, setHsDeauth] = useState(false)
  const [pmkDuration, setPmkDuration] = useState(60)
  const [deauthCount, setDeauthCount] = useState(10)
  const [deauthClient, setDeauthClient] = useState('')
  const [actionStatus, setActionStatus] = useState<string | null>(null)

  useEffect(() => {
    async function loadData() {
      if (!bssid) return
      try {
        const apData = await discoveryApi.accessPoint(bssid)
        setAp(apData)
        
        const allClients = await discoveryApi.clients()
        setClients(allClients.filter(c => c.associated_bssid?.toLowerCase() === bssid.toLowerCase()))
        
        // Scope check
        const engagements = (await api.get('/engagements').catch(() => [])) as any[]
        const activeEngagement = engagements.find(e => e.status === 'active')
        if (activeEngagement && activeEngagement.scope) {
          // simplified scope check
          setInScope(apData.in_scope)
        }
      } catch (err: any) {
        setError(err.message || 'Error loading AP')
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [bssid])

  const handleCaptureHandshake = async () => {
    if (!ap) return
    try {
      setActionStatus('Iniciando captura de Handshake...')
      await handshakeApi.startCapture({
        bssid: ap.bssid,
        channel: ap.channel,
        duration: hsDuration,
        deauth: hsDeauth
      })
      setActionStatus('Captura de Handshake iniciada exitosamente.')
    } catch (err: any) {
      setActionStatus(`Error: ${err.message}`)
    }
  }

  const handleCapturePMKID = async () => {
    if (!ap) return
    try {
      setActionStatus('Iniciando captura de PMKID...')
      await pmkidApi.startCapture({
        bssid: ap.bssid,
        channel: ap.channel,
        duration: pmkDuration
      })
      setActionStatus('Captura PMKID iniciada exitosamente.')
    } catch (err: any) {
      setActionStatus(`Error: ${err.message}`)
    }
  }

  const handleDeauth = async () => {
    if (!ap) return
    try {
      setActionStatus('Enviando deauth...')
      await deauthApi.send({
        bssid: ap.bssid,
        client_mac: deauthClient || undefined,
        count: deauthCount,
        channel: ap.channel
      })
      setActionStatus('Deauth enviado exitosamente.')
    } catch (err: any) {
      setActionStatus(`Error: ${err.message}`)
    }
  }

  const handleWpsAttack = async (type: string) => {
    if (!ap) return
    try {
      setActionStatus(`Iniciando ataque WPS (${type})...`)
      await wpsApi.attack({
        bssid: ap.bssid,
        channel: ap.channel,
        type: type
      })
      setActionStatus(`Ataque WPS (${type}) iniciado exitosamente.`)
    } catch (err: any) {
      setActionStatus(`Error: ${err.message}`)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando detalles del AP..." />
  if (error || !ap) return <div className="callout callout-error">{error || 'AP no encontrado'}</div>

  const signalPercent = Math.max(0, Math.min(100, ((ap.signal ?? -100) + 100) * 2))
  const signalColor = (ap.signal ?? -100) > -65 ? 'var(--green)' : (ap.signal ?? -100) > -80 ? 'var(--yellow)' : 'var(--red)'

  return (
    <div>
      <div className="detail-header" style={{ alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button className="btn btn-secondary btn-icon" onClick={() => navigate('/discovery')}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {ap.ssid || '<SSID Oculto>'}
              {inScope ? (
                <span className="badge badge-active" style={{ fontSize: 10 }}>IN SCOPE</span>
              ) : (
                <span className="badge badge-draft" style={{ fontSize: 10 }}>OUT OF SCOPE</span>
              )}
            </h1>
            <div className="subtitle" style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)' }}>
              {ap.bssid}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card" style={{ background: 'linear-gradient(145deg, var(--bg-card) 0%, rgba(18, 22, 36, 0.6) 100%)' }}>
          <div className="card-header">
            <div className="card-title">Señal y Seguridad</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ flex: 1, height: 8, background: 'var(--bg-tertiary)', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${signalPercent}%`, height: '100%', background: signalColor, borderRadius: 4 }} />
              </div>
              <span style={{ fontSize: 16, fontWeight: 700, color: signalColor, fontFamily: 'JetBrains Mono, monospace', width: 60, textAlign: 'right' }}>
                {ap.signal != null ? `${ap.signal} dBm` : '—'}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span className={`badge ${ap.protocol?.includes('WPA3') ? 'badge-info' : ap.protocol?.includes('WPA2') ? 'badge-open' : 'badge-draft'}`} style={{ fontSize: 14, padding: '6px 16px' }}>
                {ap.protocol || 'OPEN'}
              </span>
              {ap.wps && <span className="badge badge-medium" style={{ fontSize: 14, padding: '6px 16px' }}>WPS Habilitado</span>}
              <span className={`status-pill ${ap.pmf === 'required' ? 'active' : ap.pmf === 'optional' ? 'draft' : 'inactive'}`}>
                PMF: {ap.pmf !== 'unknown' ? ap.pmf : '—'}
              </span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Detalles Técnicos</div>
          </div>
          <div className="detail-grid" style={{ marginBottom: 0 }}>
            <div>
              <div className="detail-label">Canal</div>
              <div className="detail-value" style={{ fontWeight: 700 }}>{ap.channel ?? '—'}</div>
            </div>
            <div>
              <div className="detail-label">Banda / Frecuencia</div>
              <div className="detail-value">{ap.band || '—'} / {ap.frequency ? `${ap.frequency} MHz` : '—'}</div>
            </div>
            <div>
              <div className="detail-label">AKM / Cipher</div>
              <div className="detail-value" style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{ap.akm || '—'} / {ap.cipher || '—'}</div>
            </div>
            <div>
              <div className="detail-label">Fabricante</div>
              <div className="detail-value">{ap.vendor || 'Desconocido'}</div>
            </div>
          </div>
        </div>
      </div>

      {actionStatus && (
        <div className="callout callout-info" style={{ animation: 'pulse 2s infinite' }}>
          {actionStatus}
        </div>
      )}

      <h3 style={{ fontSize: 18, marginBottom: 16, fontWeight: 600 }}>Panel de Acción</h3>
      <div className="grid grid-3" style={{ marginBottom: 32 }}>
        
        {/* Capturar Handshake */}
        <div className="card" style={{ borderTop: '3px solid var(--accent)' }}>
          <div className="card-header">
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              🎯 Capturar Handshake
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Duración (s)</label>
            <input type="number" className="form-input" value={hsDuration} onChange={(e) => setHsDuration(Number(e.target.value))} />
          </div>
          <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" id="hsDeauth" checked={hsDeauth} onChange={(e) => setHsDeauth(e.target.checked)} />
            <label htmlFor="hsDeauth" style={{ fontSize: 13, cursor: 'pointer' }}>Deauth asisitido</label>
          </div>
          <button className="btn btn-primary" style={{ width: '100%' }} onClick={handleCaptureHandshake}>
            Iniciar Captura EAPOL
          </button>
        </div>

        {/* Capturar PMKID */}
        <div className="card" style={{ borderTop: '3px solid var(--purple)' }}>
          <div className="card-header">
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              🔑 Capturar PMKID
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Duración (s)</label>
            <input type="number" className="form-input" value={pmkDuration} onChange={(e) => setPmkDuration(Number(e.target.value))} />
          </div>
          <button className="btn btn-primary" style={{ width: '100%', background: 'linear-gradient(135deg, #d500f9 0%, #aa00ff 100%)' }} onClick={handleCapturePMKID}>
            Iniciar Captura PMKID
          </button>
        </div>

        {/* Deauth Controlada */}
        <div className="card" style={{ borderTop: '3px solid var(--orange)' }}>
          <div className="card-header">
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              ⚡ Deauth Controlada
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Cliente (MAC opcional)</label>
            <select className="form-select" value={deauthClient} onChange={(e) => setDeauthClient(e.target.value)}>
              <option value="">Broadcast (Todos)</option>
              {clients.map(c => (
                <option key={c.mac} value={c.mac}>{c.mac} ({c.vendor || 'Desconocido'})</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Paquetes: {deauthCount}</label>
            <input type="range" min="1" max="50" className="form-input" value={deauthCount} onChange={(e) => setDeauthCount(Number(e.target.value))} style={{ padding: 0 }} />
          </div>
          <button className="btn btn-primary" style={{ width: '100%', background: 'linear-gradient(135deg, #ff9100 0%, #ff6d00 100%)' }} onClick={handleDeauth}>
            Enviar Deauth
          </button>
        </div>

        {/* Ataque WPS */}
        {ap.wps && (
          <div className="card" style={{ borderTop: '3px solid var(--yellow)' }}>
            <div className="card-header">
              <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                📡 Ataque WPS
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <button className="btn btn-secondary" onClick={() => handleWpsAttack('pixie-dust')}>Pixie-Dust</button>
              <button className="btn btn-secondary" onClick={() => handleWpsAttack('brute-force')}>Fuerza Bruta</button>
              <button className="btn btn-secondary" onClick={() => handleWpsAttack('bully')}>Bully</button>
            </div>
          </div>
        )}
      </div>

      <h3 style={{ fontSize: 18, marginBottom: 16, fontWeight: 600 }}>Clientes Conectados ({clients.length})</h3>
      <div className="card" style={{ padding: 0, marginBottom: 24 }}>
        {clients.length === 0 ? (
          <div className="empty-state">
            <p>No se han detectado clientes asociados a este AP.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>MAC</th>
                  <th>Fabricante</th>
                  <th>Señal</th>
                  <th>Primera vista</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((c) => (
                  <tr key={c.mac} className="clickable" onClick={() => navigate(`/discovery/client/${encodeURIComponent(c.mac)}`)}>
                    <td style={{ fontFamily: 'monospace', fontSize: 13, color: 'var(--accent)' }}>{c.mac}</td>
                    <td>{c.vendor || '—'}</td>
                    <td>{c.signal != null ? `${c.signal} dBm` : '—'}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{c.first_seen ? new Date(c.first_seen).toLocaleString() : '—'}</td>
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
