import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { crackingApi, type DictionaryInfo, type RuleInfo } from '../../api/cracking'

type Tab = 'dictionaries' | 'rules'

export function CrackingResources() {
  const [tab, setTab] = useState<Tab>('dictionaries')
  const [dicts, setDicts] = useState<DictionaryInfo[]>([])
  const [rules, setRules] = useState<RuleInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      try {
        const [d, r] = await Promise.all([
          crackingApi.dictionaries(),
          crackingApi.rules(),
        ])
        setDicts(d)
        setRules(r)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  function formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  }

  if (loading) return <LoadingSpinner text="Cargando recursos..." />

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Recursos de cracking</h1>
          <div className="subtitle">Diccionarios y reglas disponibles en el sistema</div>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}

      <div className="tabs" style={{ marginBottom: 16 }}>
        <div className={'tab' + (tab === 'dictionaries' ? ' active' : '')} onClick={() => setTab('dictionaries')}>
          Diccionarios ({dicts.length})
        </div>
        <div className={'tab' + (tab === 'rules' ? ' active' : '')} onClick={() => setTab('rules')}>
          Reglas ({rules.length})
        </div>
      </div>

      {tab === 'dictionaries' && (
        <div className="card" style={{ padding: 0 }}>
          {dicts.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
              <p>No hay diccionarios disponibles.</p>
              <p style={{ fontSize: 12, marginTop: 8 }}>Instala wordlists en el sistema (rockyou.txt, etc.)</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr><th>Nombre</th><th>Ruta</th><th>Tamaño</th><th>Líneas</th></tr>
                </thead>
                <tbody>
                  {dicts.map(d => (
                    <tr key={d.name}>
                      <td style={{ fontWeight: 500 }}>{d.name}</td>
                      <td style={{ fontSize: 11, fontFamily: 'monospace', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.path}</td>
                      <td>{formatSize(d.size_bytes)}</td>
                      <td>{d.line_count != null ? d.line_count.toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'rules' && (
        <div className="card" style={{ padding: 0 }}>
          {rules.length === 0 ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
              <p>No hay reglas disponibles.</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr><th>Nombre</th><th>Ruta</th><th>Tamaño</th><th>Reglas</th></tr>
                </thead>
                <tbody>
                  {rules.map(r => (
                    <tr key={r.name}>
                      <td style={{ fontWeight: 500 }}>{r.name}</td>
                      <td style={{ fontSize: 11, fontFamily: 'monospace', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.path}</td>
                      <td>{formatSize(r.size_bytes)}</td>
                      <td>{r.rule_count != null ? r.rule_count.toLocaleString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
