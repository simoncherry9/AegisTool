import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { discoveryApi, type ClientSummary } from '../../api/discovery'
import { deauthApi } from '../../api/deauth'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { interfacesApi } from '../../api/interfaces'

export function ClientDetail() {
  const { mac } = useParams<{ mac: string }>()
  const navigate = useNavigate()
  
  const [client, setClient] = useState<ClientSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionStatus, setActionStatus] = useState<string | null>(null)
  const [currentInterface, setCurrentInterface] = useState<string | null>(null)

  useEffect(() => {
    async function loadData() {
      if (!mac) return
      try {
        const allClients = await discoveryApi.clients()
        const found = allClients.find(c => c.mac.toLowerCase() === decodeURIComponent(mac).toLowerCase())
        if (found) {
          setClient(found)
        } else {
          setError('Cliente no encontrado')
        }
        
        const status = await discoveryApi.status().catch(() => null)
        if (status?.interface) {
          setCurrentInterface(status.interface)
        } else {
          const ifcs = await interfacesApi.list().catch(() => [])
          const mon = ifcs.find(i => i.monitor_mode) || ifcs[0]
          if (mon) setCurrentInterface(mon.name)
        }
      } catch (err: any) {
        setError(err.message || 'Error loading Client')
      } finally {
        setLoading(false)
      }
    }
    loadData()

    if (!mac) return
    const interval = setInterval(async () => {
      try {
        const allClients = await discoveryApi.clients()
        const found = allClients.find(c => c.mac.toLowerCase() === decodeURIComponent(mac).toLowerCase())
        if (found) setClient(found)
      } catch (err) {
        // ignore
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [mac])

  const handleDeauth = async () => {
    if (!client || !client.associated_bssid) {
      setActionStatus('Error: El cliente no está asociado a ningún AP conocido.')
      return
    }
    if (!currentInterface) {
      setActionStatus('Error: No hay interfaz disponible.')
      return
    }
    try {
      setActionStatus('Enviando deauth dirigida...')
      await deauthApi.send({
        interface: currentInterface,
        bssid: client.associated_bssid,
        client_mac: client.mac,
        count: 10
      })
      setActionStatus('Deauth enviado exitosamente.')
    } catch (err: any) {
      setActionStatus(`Error: ${err.message}`)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando detalles del cliente..." />
  if (error || !client) return <div className="callout callout-error">{error || 'Cliente no encontrado'}</div>

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
            <h1>Cliente {client.vendor || 'Desconocido'}</h1>
            <div className="subtitle" style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)', fontSize: 16 }}>
              {client.mac}
              {client.randomized && <span className="badge badge-draft" style={{ marginLeft: 8 }}>MAC Aleatoria</span>}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">Información de Conexión</div>
          </div>
          <div className="detail-grid" style={{ marginBottom: 0 }}>
            <div>
              <div className="detail-label">AP Asociado (BSSID)</div>
              <div className="detail-value">
                {client.associated_bssid ? (
                  <Link to={`/discovery/ap/${client.associated_bssid}`} style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>
                    {client.associated_bssid}
                  </Link>
                ) : 'No asociado'}
              </div>
            </div>
            <div>
              <div className="detail-label">SSID Asociado</div>
              <div className="detail-value">{client.associated_ssid || '—'}</div>
            </div>
            <div>
              <div className="detail-label">Señal</div>
              <div className="detail-value">{client.signal != null ? `${client.signal} dBm` : '—'}</div>
            </div>
            <div>
              <div className="detail-label">Controlado</div>
              <div className="detail-value">{client.controlled ? 'Sí' : 'No'}</div>
            </div>
          </div>
        </div>

        <div className="card" style={{ borderTop: '3px solid var(--orange)' }}>
          <div className="card-header">
            <div className="card-title">Acciones</div>
          </div>
          {actionStatus && (
            <div className="callout callout-info" style={{ marginBottom: 16 }}>
              {actionStatus}
            </div>
          )}
          <button 
            className="btn btn-primary" 
            style={{ width: '100%', background: 'linear-gradient(135deg, #ff9100 0%, #ff6d00 100%)' }} 
            onClick={handleDeauth}
            disabled={!client.associated_bssid}
          >
            ⚡ Enviar Deauth Dirigida (10 pkts)
          </button>
          {!client.associated_bssid && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, textAlign: 'center' }}>
              Requiere asociación a un AP para enviar deauth.
            </div>
          )}
        </div>
      </div>

      {client.probe_requests && client.probe_requests.length > 0 && (
        <>
          <h3 style={{ fontSize: 18, marginBottom: 16, fontWeight: 600 }}>Probe Requests (Historial de redes)</h3>
          <div className="card">
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {client.probe_requests.map((probe, i) => (
                <span key={i} className="badge badge-info" style={{ padding: '6px 12px', fontSize: 13 }}>
                  {probe}
                </span>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
