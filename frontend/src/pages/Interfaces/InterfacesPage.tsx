import { useEffect, useState } from 'react'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { interfacesApi, type WirelessInterface, type InterfaceDiagnostic, type InterfacePrepareResult } from '../../api/interfaces'

export function InterfacesPage() {
  const [ifaces, setIfaces] = useState<WirelessInterface[]>([])
  const [diagnostic, setDiagnostic] = useState<InterfaceDiagnostic | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [preparing, setPreparing] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [ifcs, diag] = await Promise.all([
          interfacesApi.list(),
          interfacesApi.diagnose().catch(() => null),
        ])
        setIfaces(ifcs)
        setDiagnostic(diag)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  async function handlePrepare(name: string) {
    setPreparing(name)
    setActionMsg(null)
    setActionError(null)
    try {
      const result = await interfacesApi.prepare(name)
      if (result.success) {
        setActionMsg('Interfaz ' + name + ' preparada: ' + result.mode)
        setIfaces(ifaces.map(i => i.name === name ? { ...i, monitor_mode: true, mode: result.mode || i.mode } : i))
      } else {
        setActionError('Error al preparar ' + name + ': ' + (result.error || 'desconocido'))
      }
    } catch (e: any) {
      setActionError('Error: ' + e.message)
    } finally {
      setPreparing(null)
    }
  }

  async function handleRestore(name: string) {
    setActionMsg(null)
    setActionError(null)
    try {
      const result = await interfacesApi.restore(name)
      setActionMsg('Interfaz ' + name + ' restaurada' + (result.restored_state ? ' (' + result.restored_state + ')' : ''))
      const ifcs = await interfacesApi.list()
      setIfaces(ifcs)
    } catch (e: any) {
      setActionError('Error: ' + e.message)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando interfaces..." />

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Interfaces de red</h1>
          <div className="subtitle">Gestión de interfaces inalámbricas</div>
        </div>
        <div className="detail-actions">
          <button className="btn btn-sm btn-secondary" onClick={() => window.location.reload()}>↻ Recargar</button>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}
      {actionMsg && <div className="callout" style={{ borderLeft: '3px solid var(--green)' }}>{actionMsg}</div>}
      {actionError && <div className="callout callout-error">{actionError}</div>}

      {diagnostic && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header"><div className="card-title">Diagnóstico del sistema</div></div>
          <div style={{ padding: '0 20px 16px', display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 13 }}>
            <div>Health: <strong style={{ color: diagnostic.health === 'OK' ? 'var(--green)' : 'var(--red)' }}>{diagnostic.health}</strong></div>
            {diagnostic.warnings?.length > 0 && (
              <div style={{ color: 'var(--yellow)' }}>
                ⚠ Advertencias: {diagnostic.warnings.length}
              </div>
            )}
            {diagnostic.errors?.length > 0 && (
              <div style={{ color: 'var(--red)' }}>
                ✗ Errores: {diagnostic.errors.length}
              </div>
            )}
          </div>
          {diagnostic.errors?.length > 0 && (
            <div style={{ padding: '0 20px 16px', fontSize: 12, color: 'var(--red)' }}>
              {diagnostic.errors.map((e, i) => <div key={i}>• {e}</div>)}
            </div>
          )}
        </div>
      )}

      {ifaces.length === 0 ? (
        <div className="card">
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
            <p>No se detectaron interfaces inalámbricas.</p>
            <p style={{ fontSize: 12, marginTop: 8 }}>Verifica que el hardware esté conectado y los drivers instalados.</p>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Nombre</th><th>MAC</th><th>Estado</th><th>Modo</th><th>PHY</th>
                  <th>Driver</th><th>Canal</th><th>Banda</th><th>Potencia</th>
                  <th>Señal</th><th>Monitor</th><th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {ifaces.map(iface => (
                  <tr key={iface.name}>
                    <td style={{ fontWeight: 600 }}>{iface.name}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{iface.mac || '—'}</td>
                    <td><span style={{ color: iface.state === 'up' ? 'var(--green)' : 'var(--red)', fontSize: 12, fontWeight: 600 }}>{iface.state}</span></td>
                    <td style={{ fontSize: 12 }}>{iface.mode || '—'}</td>
                    <td>{iface.phy != null ? 'phy' + iface.phy : '—'}</td>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{iface.driver || '—'}</td>
                    <td>{iface.channel ?? '—'}</td>
                    <td style={{ fontSize: 12 }}>{iface.band || '—'}</td>
                    <td style={{ fontSize: 12 }}>{iface.tx_power != null ? iface.tx_power + ' dBm' : '—'}</td>
                    <td>{iface.signal != null ? iface.signal + ' dBm' : '—'}</td>
                    <td>{iface.monitor_mode ? <span style={{ color: 'var(--green)' }}>✓</span> : '—'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {!iface.monitor_mode ? (
                          <button className="btn btn-sm btn-secondary"
                            disabled={preparing === iface.name}
                            style={{ fontSize: 10, padding: '2px 8px' }}
                            onClick={() => handlePrepare(iface.name)}>
                            {preparing === iface.name ? '...' : '🔧 Preparar'}
                          </button>
                        ) : (
                          <button className="btn btn-sm btn-danger"
                            style={{ fontSize: 10, padding: '2px 8px' }}
                            onClick={() => handleRestore(iface.name)}>
                            Restaurar
                          </button>
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

      {ifaces.map(iface => (
        <div key={iface.name + '-caps'} className="card" style={{ marginTop: 12 }}>
          <div className="card-header"><div className="card-title">Capacidades: {iface.name}</div></div>
          {iface.capabilities?.length > 0 ? (
            <div style={{ padding: '0 20px 16px', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {iface.capabilities.map((cap, i) => (
                <span key={i} style={{ background: 'var(--bg-secondary)', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontFamily: 'monospace' }}>{cap}</span>
              ))}
            </div>
          ) : (
            <div style={{ padding: '0 20px 16px', color: 'var(--text-muted)', fontSize: 12 }}>Sin información de capacidades</div>
          )}
        </div>
      ))}
    </div>
  )
}
