import { useEffect, useState } from 'react'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { toolsApi, type ToolsCheckResult } from '../../api/tools'

const CATEGORY_LABELS: Record<string, string> = {
  capture: 'Captura e inyección',
  cracking: 'Cracking',
  interface: 'Interfaces',
  analysis: 'Análisis',
  utility: 'Utilidades',
}

const CATEGORY_ORDER = ['capture', 'cracking', 'interface', 'analysis', 'utility']

export function ToolsCheck() {
  const [result, setResult] = useState<ToolsCheckResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    toolsApi.check()
      .then(setResult)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner text="Verificando herramientas..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>
  if (!result) return null

  const grouped = CATEGORY_ORDER.map(cat => ({
    category: cat,
    label: CATEGORY_LABELS[cat] || cat,
    tools: result.tools.filter(t => t.category === cat),
  }))

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Herramientas del sistema</h1>
          <div className="subtitle">
            {result.installed}/{result.total} herramientas instaladas ({result.os})
          </div>
        </div>
        <div className="detail-actions">
          <button className="btn btn-secondary" onClick={() => window.location.reload()}>
            Re-verificar
          </button>
        </div>
      </div>

      {/* Sudo Credential Card */}
      <SudoConfigCard />

      {/* Summary badges */}
      <div className="grid grid-3" style={{ marginBottom: 24 }}>
        <div className="card stat-card" style={{ borderLeft: '3px solid var(--green)' }}>
          <div className="stat-value" style={{ color: 'var(--green)' }}>{result.installed}</div>
          <div className="stat-label">Instaladas</div>
        </div>
        <div className="card stat-card" style={{ borderLeft: '3px solid var(--red)' }}>
          <div className="stat-value" style={{ color: 'var(--red)' }}>{result.missing}</div>
          <div className="stat-label">Faltantes</div>
        </div>
        <div className="card stat-card" style={{ borderLeft: '3px solid var(--accent)' }}>
          <div className="stat-value">{result.total}</div>
          <div className="stat-label">Total</div>
        </div>
      </div>

      {grouped.map(group => {
        const installed = group.tools.filter(t => t.installed).length
        const total = group.tools.length
        return (
          <div key={group.category} className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <div>
                <div className="card-title">{group.label}</div>
                <div className="card-subtitle">{installed}/{total} instaladas</div>
              </div>
            </div>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Herramienta</th>
                    <th>Binario</th>
                    <th>Estado</th>
                    <th>Versión</th>
                  </tr>
                </thead>
                <tbody>
                  {group.tools.map(tool => (
                    <tr key={tool.binary}>
                      <td style={{ fontWeight: 500 }}>{tool.name}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{tool.binary}</td>
                      <td>
                        {tool.installed
                          ? <span className="badge badge-active">✓ Instalado</span>
                          : <span className="badge badge-closed">✗ No encontrado</span>
                        }
                      </td>
                      <td style={{ color: 'var(--text-muted)', fontSize: 13, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {tool.version || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      })}

      {result.missing > 0 && (
        <div className="callout" style={{ marginTop: 16 }}>
          <strong>⚠ Algunas herramientas no están instaladas.</strong>
          <p style={{ margin: '4px 0 0', fontSize: 13 }}>
            En Kali Linux: <code style={{ background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: 4 }}>sudo apt install aircrack-ng hcxtools hashcat iw tshark nmap</code>
          </p>
        </div>
      )}
    </div>
  )
}

function SudoConfigCard() {
  const [sudoPass, setSudoPass] = useState('')
  const [configured, setConfigured] = useState(false)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/v1/tools/sudo-status')
      .then(res => res.json())
      .then(data => {
        if (data.configured) setConfigured(true)
      })
      .catch(() => {})
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sudoPass) return
    setLoading(true)
    setMessage(null)

    try {
      const res = await fetch('/api/v1/tools/sudo-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: sudoPass }),
      })
      const data = await res.json()
      if (res.ok) {
        setConfigured(true)
        setSudoPass('')
        setMessage('Contraseña sudo de Kali cifrada y almacenada correctamente.')
      } else {
        setMessage(data.detail || 'Error al guardar contraseña')
      }
    } catch {
      setMessage('Error al conectar con el servidor')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card" style={{ marginBottom: 24, borderLeft: '3px solid var(--purple)' }}>
      <div className="card-header">
        <div>
          <div className="card-title">Configuración de Privilegios Elevados (sudo Kali)</div>
          <div className="card-subtitle">
            Almacenamiento cifrado de la clave sudo para ejecutar adaptadores que requieren el helper privilegiado.
          </div>
        </div>
        <span className={`status-pill ${configured ? 'active' : 'inactive'}`}>
          {configured ? '✓ Configurado (Cifrado)' : 'Sin Configurar'}
        </span>
      </div>
      <div style={{ padding: '0 16px 16px' }}>
        {message && <div className="callout callout-info" style={{ marginBottom: 12 }}>{message}</div>}
        <form onSubmit={handleSave} style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <input
            type="password"
            className="form-input"
            placeholder="Contraseña sudo de Kali Linux"
            value={sudoPass}
            onChange={(e) => setSudoPass(e.target.value)}
            style={{ maxWidth: 320 }}
          />
          <button type="submit" className="btn btn-primary" disabled={loading || !sudoPass}>
            {loading ? 'Guardando...' : configured ? 'Actualizar Contraseña' : 'Guardar Contraseña'}
          </button>
        </form>
      </div>
    </div>
  )
}
