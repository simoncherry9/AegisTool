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
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [dictionaryName, setDictionaryName] = useState('')
  const [dictionaryWords, setDictionaryWords] = useState('')
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

  async function refreshDictionaries() {
    setDicts(await crackingApi.dictionaries())
  }

  async function handleCreateDictionary(event: React.FormEvent) {
    event.preventDefault()
    const words = dictionaryWords.split(/\r?\n/).map(word => word.trim()).filter(Boolean)
    if (!dictionaryName.trim() || words.length === 0) {
      setError('Escribe un nombre y al menos una palabra')
      return
    }
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const created = await crackingApi.createDictionary(dictionaryName.trim(), words)
      setDictionaryName('')
      setDictionaryWords('')
      await refreshDictionaries()
      setNotice(`${created.name} creado con ${created.line_count ?? words.length} entradas`)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDecompress(dictionary: DictionaryInfo) {
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const extracted = await crackingApi.decompressDictionary(dictionary.path)
      await refreshDictionaries()
      setNotice(`${dictionary.name} se descomprimió como ${extracted.name}`)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(dictionary: DictionaryInfo) {
    if (!confirm(`¿Eliminar el diccionario personalizado ${dictionary.name}?`)) return
    setSaving(true)
    setError(null)
    try {
      await crackingApi.deleteDictionary(dictionary.name)
      await refreshDictionaries()
      setNotice(`${dictionary.name} eliminado`)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

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
      {notice && <div className="callout callout-success">{notice}</div>}

      <div className="tabs" style={{ marginBottom: 16 }}>
        <div className={'tab' + (tab === 'dictionaries' ? ' active' : '')} onClick={() => setTab('dictionaries')}>
          Diccionarios ({dicts.length})
        </div>
        <div className={'tab' + (tab === 'rules' ? ' active' : '')} onClick={() => setTab('rules')}>
          Reglas ({rules.length})
        </div>
      </div>

      {tab === 'dictionaries' && (
        <>
        <form className="card" style={{ marginBottom: 16 }} onSubmit={handleCreateDictionary}>
          <div className="card-header">
            <div>
              <div className="card-title">Crear diccionario personalizado</div>
              <div className="subtitle">Una palabra o candidato por línea; se eliminan vacíos y duplicados.</div>
            </div>
          </div>
          <div className="grid grid-2">
            <div className="form-group">
              <label className="form-label">Nombre</label>
              <input className="form-input" value={dictionaryName} maxLength={80} placeholder="clientes-argentina" onChange={e => setDictionaryName(e.target.value)} />
            </div>
            <div className="form-group" style={{ gridRow: 'span 2' }}>
              <label className="form-label">Palabras</label>
              <textarea className="form-input" rows={8} value={dictionaryWords} placeholder={'Empresa2026\nSucursal01\nMarca1234'} onChange={e => setDictionaryWords(e.target.value)} />
            </div>
          </div>
          <button className="btn btn-primary" disabled={saving} type="submit">
            {saving ? 'Guardando...' : 'Crear diccionario'}
          </button>
        </form>

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
                  <tr><th>Nombre</th><th>Tipo</th><th>Ruta</th><th>Tamaño</th><th>Líneas</th><th>Acciones</th></tr>
                </thead>
                <tbody>
                  {dicts.map(d => (
                    <tr key={d.path}>
                      <td style={{ fontWeight: 500 }}>{d.name}</td>
                      <td>{d.compressed ? <span className="badge badge-draft">Comprimido</span> : d.custom ? <span className="badge badge-info">Personalizado</span> : <span className="badge">Sistema</span>}</td>
                      <td style={{ fontSize: 11, fontFamily: 'monospace', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.path}</td>
                      <td>{formatSize(d.size_bytes)}</td>
                      <td>{d.line_count != null ? d.line_count.toLocaleString() : '—'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: 6 }}>
                          {d.compressed && <button className="btn btn-sm btn-primary" disabled={saving || d.name.endsWith('.7z')} onClick={() => handleDecompress(d)}>Descomprimir</button>}
                          {d.custom && !d.compressed && <button className="btn btn-sm btn-danger" disabled={saving} onClick={() => handleDelete(d)}>Eliminar</button>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        </>
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
