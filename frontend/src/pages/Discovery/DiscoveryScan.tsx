import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { discoveryApi, type AccessPoint, type ClientSummary, type ScanStatus, type ScanConfig } from '../../api/discovery'
import { interfacesApi, type WirelessInterface } from '../../api/interfaces'

type ScanPhase = 'idle' | 'preparing' | 'scanning' | 'stopping'

export function DiscoveryScan() {
  const [interfaces, setInterfaces] = useState<WirelessInterface[]>([])
  const [aps, setAps] = useState<AccessPoint[]>([])
  const [clients, setClients] = useState<ClientSummary[]>([])
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null)
  const [phase, setPhase] = useState<ScanPhase>('idle')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'aps' | 'clients'>('aps')
  const navigate = useNavigate()

  // Scan config state
  const [selectedIface, setSelectedIface] = useState('')
  const [scanDuration, setScanDuration] = useState(60)
  const [selectedBand, setSelectedBand] = useState('')
  const [prepareMsg, setPrepareMsg] = useState<string | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Cargar interfaces y datos iniciales
  const loadAll = useCallback(async () => {
    try {
      const [ifaces, apsData, clientsData, statusData] = await Promise.all([
        interfacesApi.list().catch(() => []),
        discoveryApi.accessPoints({ limit: 500 }).catch(() => [] as AccessPoint[]),
        discoveryApi.clients().catch(() => [] as ClientSummary[]),
        discoveryApi.status().catch(() => null),
      ])
      setInterfaces(ifaces)
      setAps(apsData)
      setClients(clientsData)
      setScanStatus(statusData)

      // Pre-seleccionar primera interfaz disponible
      if (!selectedIface && ifaces.length > 0) {
        setSelectedIface(ifaces[0].name)
      }

      // Si ya hay un escaneo corriendo, pasar a fase scanning
      if (statusData?.running) {
        setPhase('scanning')
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // Polling de estado mientras se escanea
  useEffect(() => {
    if (phase === 'scanning') {
      // Limpiar polling anterior si lo hay
      if (pollRef.current) clearInterval(pollRef.current)

      pollRef.current = setInterval(async () => {
        try {
          const [statusData, apsData, clientsData] = await Promise.all([
            discoveryApi.status(),
            discoveryApi.accessPoints({ limit: 500 }),
            discoveryApi.clients(),
          ])
          setScanStatus(statusData)
          setAps(apsData)
          setClients(clientsData)

          // Si ya terminó, detener polling
          if (!statusData.running) {
            setPhase('idle')
            if (pollRef.current) clearInterval(pollRef.current)
            pollRef.current = null
          }
        } catch {
          // ignorar errores de polling
        }
      }, 2000)
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [phase])

  async function handlePrepare() {
    if (!selectedIface) return
    setPrepareMsg(null)
    setPhase('preparing')
    setError(null)
    try {
      const result = await interfacesApi.prepare(selectedIface)
      if (result.mode_set) {
        setPrepareMsg(`Interfaz preparada → ${result.monitor_interface} (monitor mode)`)
        // Actualizar la interfaz seleccionada si cambió de nombre
        if (result.monitor_interface !== selectedIface) {
          setSelectedIface(result.monitor_interface)
        }
        // Recargar interfaces
        const ifaces = await interfacesApi.list().catch(() => [])
        setInterfaces(ifaces)
      } else {
        setError('No se pudo activar monitor mode')
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e.message || 'Error al preparar interfaz'
      setError(detail)
    } finally {
      setPhase('idle')
    }
  }

  async function handleStartScan() {
    if (!selectedIface) {
      setError('Selecciona una interfaz primero')
      return
    }
    setError(null)
    setPhase('preparing')

    const config: ScanConfig = {
      interface: selectedIface,
      duration: scanDuration || undefined,
    }
    if (selectedBand) config.band = selectedBand

    try {
      const status = await discoveryApi.start(config)
      setScanStatus(status)
      setPhase('scanning')
    } catch (e: any) {
      setError(e.message || 'Error al iniciar escaneo')
      setPhase('idle')
    }
  }

  async function handleStopScan() {
    setPhase('stopping')
    setError(null)
    try {
      const status = await discoveryApi.stop()
      setScanStatus(status)
      setPhase('idle')
      // Recargar datos finales
      const [apsData, clientsData] = await Promise.all([
        discoveryApi.accessPoints({ limit: 500 }),
        discoveryApi.clients(),
      ])
      setAps(apsData)
      setClients(clientsData)
    } catch (e: any) {
      setError(e.message || 'Error al detener escaneo')
      setPhase('idle')
    }
  }

  function formatUptime(seconds: number | null): string {
    if (seconds == null) return '—'
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  if (loading) return <LoadingSpinner text="Cargando interfaces..." />

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Discovery</h1>
          <div className="subtitle">Escaneo de redes y detección de dispositivos</div>
        </div>
      </div>

      {/* Panel de control de escaneo */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Control de escaneo</div>
            <div className="card-subtitle">Configura la interfaz y comienza el descubrimiento</div>
          </div>
          {scanStatus?.running && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="badge badge-active" style={{ animation: 'pulse 1.5s infinite' }}>
                ● ESCANEANDO
              </span>
            </div>
          )}
        </div>

        {error && <div className="callout callout-error">{error}</div>}
        {prepareMsg && <div className="callout" style={{ borderLeft: '3px solid var(--green)' }}>{prepareMsg}</div>}

        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {/* Selector de interfaz */}
          <div className="form-group" style={{ flex: '1 1 200px', marginBottom: 0 }}>
            <label className="form-label">Interfaz inalámbrica</label>
            <select className="form-select" value={selectedIface}
              onChange={(e) => { setSelectedIface(e.target.value); setPrepareMsg(null) }}>
              {interfaces.length === 0 && <option value="">No hay interfaces disponibles</option>}
              {interfaces.map((iface) => (
                <option key={iface.name} value={iface.name}>
                  {iface.name} {iface.monitor_mode ? '(monitor)' : `(${iface.mode || iface.state})`}
                </option>
              ))}
            </select>
            {interfaces.length > 0 && !interfaces.find(i => i.name === selectedIface)?.monitor_mode && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                Modo monitor requerido — usa "Preparar"
              </div>
            )}
          </div>

          {/* Duración */}
          <div className="form-group" style={{ flex: '0 1 120px', marginBottom: 0 }}>
            <label className="form-label">Duración (s)</label>
            <input className="form-input" type="number" min={10} max={600}
              value={scanDuration} onChange={(e) => setScanDuration(Number(e.target.value))}
              disabled={phase === 'scanning'} />
          </div>

          {/* Banda */}
          <div className="form-group" style={{ flex: '0 1 140px', marginBottom: 0 }}>
            <label className="form-label">Banda</label>
            <select className="form-select" value={selectedBand}
              onChange={(e) => setSelectedBand(e.target.value)} disabled={phase === 'scanning'}>
              <option value="">Todas</option>
              <option value="2.4 GHz">2.4 GHz</option>
              <option value="5 GHz">5 GHz</option>
              <option value="6 GHz">6 GHz</option>
            </select>
          </div>

          {/* Botones */}
          <div style={{ display: 'flex', gap: 8, paddingBottom: 1 }}>
            <button className="btn btn-secondary" onClick={handlePrepare}
              disabled={!selectedIface || phase === 'scanning' || phase === 'preparing'}
              title="Activar modo monitor en la interfaz">
              {phase === 'preparing' ? 'Preparando...' : '🔧 Preparar'}
            </button>
            {!scanStatus?.running ? (
              <button className="btn btn-primary" onClick={handleStartScan}
                disabled={!selectedIface || phase === 'preparing'}>
                ▶ Iniciar escaneo
              </button>
            ) : (
              <button className="btn btn-danger" onClick={handleStopScan}
                disabled={phase === 'stopping'}>
                ⏹ Detener
              </button>
            )}
          </div>
        </div>

        {/* Estado del escaneo */}
        {scanStatus && (
          <div style={{
            display: 'flex', gap: 24, marginTop: 16, paddingTop: 12,
            borderTop: '1px solid var(--border)', flexWrap: 'wrap',
          }}>
            <div style={{ fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>Estado: </span>
              <strong>{scanStatus.running ? 'Ejecutando' : 'Detenido'}</strong>
            </div>
            <div style={{ fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>Interfaz: </span>
              <strong>{scanStatus.interface || '—'}</strong>
            </div>
            <div style={{ fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>Canal: </span>
              <strong>{scanStatus.channel ?? '—'}</strong>
            </div>
            <div style={{ fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>Tiempo: </span>
              <strong>{formatUptime(scanStatus.uptime_seconds)}</strong>
            </div>
            <div style={{ fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>APs: </span>
              <strong style={{ color: 'var(--accent)' }}>{scanStatus.ap_count}</strong>
            </div>
            <div style={{ fontSize: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>Clientes: </span>
              <strong style={{ color: 'var(--accent)' }}>{scanStatus.client_count}</strong>
            </div>
            {scanStatus.error && (
              <div style={{ fontSize: 12, color: 'var(--red)' }}>
                ⚠ {scanStatus.error}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Pestañas APs / Clientes */}
      <div className="tabs" style={{ marginBottom: 16 }}>
        <div className={`tab${tab === 'aps' ? ' active' : ''}`} onClick={() => setTab('aps')}>
          Puntos de acceso ({aps.length})
        </div>
        <div className={`tab${tab === 'clients' ? ' active' : ''}`} onClick={() => setTab('clients')}>
          Clientes ({clients.length})
        </div>
      </div>

      {/* Tabla de APs */}
      {tab === 'aps' && (
        <div className="card" style={{ padding: 0 }}>
          {aps.length === 0 ? (
            <div className="empty-state">
              <p>No se detectaron puntos de acceso.</p>
              <p style={{ fontSize: 12, marginTop: 8, color: 'var(--text-muted)' }}>
                Selecciona una interfaz y haz clic en "Iniciar escaneo"
              </p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>SSID</th>
                    <th>BSSID</th>
                    <th>Can</th>
                    <th>Señal</th>
                    <th>Seguridad</th>
                    <th>Banda</th>
                    <th>AKM</th>
                    <th>WPS</th>
                    <th>PMF</th>
                    <th>Clientes</th>
                  </tr>
                </thead>
                <tbody>
                  {aps.map((ap, i) => {
                    const signal = ap.signal ?? -100
                    const percent = Math.max(0, Math.min(100, (signal + 100) * 2))
                    const signalColor = signal > -65 ? 'var(--green)' : signal > -80 ? 'var(--yellow)' : 'var(--red)'
                    
                    return (
                      <tr key={`${ap.bssid}-${i}`} className="clickable" onClick={() => navigate(`/discovery/ap/${ap.bssid}`)}>
                        <td style={{ fontWeight: 600, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <span style={{ color: ap.ssid ? 'var(--text-primary)' : 'var(--text-muted)', fontStyle: ap.ssid ? 'normal' : 'italic' }}>
                            {ap.ssid || '<SSID Oculto>'}
                          </span>
                          {ap.degraded && <span className="badge badge-critical" style={{ marginLeft: 6, fontSize: 9 }}>degradado</span>}
                        </td>
                        <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--accent)' }}>{ap.bssid}</td>
                        <td style={{ fontWeight: 700 }}>{ap.channel ?? '—'}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ width: 44, height: 6, background: 'var(--bg-tertiary)', borderRadius: 3, overflow: 'hidden' }}>
                              <div style={{ width: `${percent}%`, height: '100%', background: signalColor, borderRadius: 3 }} />
                            </div>
                            <span style={{ fontSize: 12, fontWeight: 600, color: signalColor, fontFamily: 'JetBrains Mono, monospace' }}>
                              {ap.signal != null ? `${ap.signal} dBm` : '—'}
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${ap.protocol?.includes('WPA3') ? 'badge-info' : ap.protocol?.includes('WPA2') ? 'badge-open' : 'badge-draft'}`}>
                            {ap.protocol || 'OPEN'}
                          </span>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{ap.band || '—'}</td>
                        <td style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-muted)' }}>{ap.akm || '—'}</td>
                        <td>
                          {ap.wps ? (
                            <span className="badge badge-medium" title="WPS Habilitado">WPS</span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>
                          )}
                        </td>
                        <td style={{ fontSize: 11 }}>
                          <span className={`status-pill ${ap.pmf === 'required' ? 'active' : ap.pmf === 'optional' ? 'draft' : 'inactive'}`}>
                            {ap.pmf !== 'unknown' ? ap.pmf : '—'}
                          </span>
                        </td>
                        <td style={{ textAlign: 'center', fontWeight: 700 }}>{ap.clients_count || 0}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tabla de Clientes */}
      {tab === 'clients' && (
        <div className="card" style={{ padding: 0 }}>
          {clients.length === 0 ? (
            <div className="empty-state">
              <p>No se detectaron clientes.</p>
              <p style={{ fontSize: 12, marginTop: 8, color: 'var(--text-muted)' }}>
                Los clientes aparecen durante el escaneo activo
              </p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>MAC</th>
                    <th>Fabricante</th>
                    <th>BSSID asociado</th>
                    <th>SSID</th>
                    <th>Señal</th>
                    <th>Probes</th>
                    <th>Aleatoria</th>
                    <th>Controlada</th>
                    <th>Primera vista</th>
                  </tr>
                </thead>
                <tbody>
                  {clients.map((c, i) => (
                    <tr key={`${c.mac}-${i}`} className="clickable" onClick={() => navigate(`/discovery/client/${encodeURIComponent(c.mac)}`)}>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{c.mac}</td>
                      <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.vendor || '—'}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{c.associated_bssid || '—'}</td>
                      <td style={{ fontSize: 12, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {c.associated_ssid || '—'}
                      </td>
                      <td>{c.signal != null ? `${c.signal} dBm` : '—'}</td>
                      <td style={{ fontSize: 12, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {c.probe_requests?.length ? c.probe_requests.join(', ') : '—'}
                      </td>
                      <td style={{ textAlign: 'center' }}>{c.randomized ? '✓' : '—'}</td>
                      <td style={{ textAlign: 'center' }}>{c.controlled ? '✓' : '—'}</td>
                      <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {c.first_seen ? new Date(c.first_seen).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Interfaces disponibles */}
      {interfaces.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Interfaces del sistema</div>
              <div className="card-subtitle">{interfaces.length} interfaz(es) detectada(s)</div>
            </div>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>Nombre</th><th>MAC</th><th>Estado</th><th>Modo</th><th>Driver</th><th>Monitor</th><th>Potencia</th></tr>
              </thead>
              <tbody>
                {interfaces.map((iface) => (
                  <tr key={iface.name}>
                    <td style={{ fontWeight: 600 }}>{iface.name}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{iface.mac || '—'}</td>
                    <td><StatusBadge status={iface.state} /></td>
                    <td style={{ fontSize: 12 }}>{iface.mode || '—'}</td>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{iface.driver || '—'}</td>
                    <td>{iface.monitor_mode ? <span className="badge badge-active">✓</span> : '—'}</td>
                    <td style={{ fontSize: 12 }}>{iface.tx_power != null ? `${iface.tx_power} dBm` : '—'}</td>
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

// Componente auxiliar inline para StatusBadge
function StatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    up: 'var(--green)',
    down: 'var(--red)',
    running: 'var(--accent)',
    idle: 'var(--text-muted)',
  }
  return (
    <span style={{
      background: (colorMap[status.toLowerCase()] || 'var(--text-muted)') + '22',
      color: colorMap[status.toLowerCase()] || 'var(--text-muted)',
      padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
    }}>
      {status}
    </span>
  )
}
