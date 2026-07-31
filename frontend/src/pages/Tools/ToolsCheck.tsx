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
