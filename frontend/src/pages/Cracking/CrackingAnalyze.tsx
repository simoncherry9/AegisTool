import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { crackingApi, type AnalyzePlan, type DictionaryInfo, type RuleInfo } from '../../api/cracking'
import { engagementsApi, type Engagement } from '../../api/engagements'

export function CrackingAnalyze() {
  const { artifactId } = useParams<{ artifactId: string }>()
  const navigate = useNavigate()
  const [plan, setPlan] = useState<AnalyzePlan | null>(null)
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [selectedEng, setSelectedEng] = useState<number | undefined>()
  const [dictionaries, setDictionaries] = useState<DictionaryInfo[]>([])
  const [rules, setRules] = useState<RuleInfo[]>([])
  const [selectedDictionary, setSelectedDictionary] = useState('')
  const [customDictPath, setCustomDictPath] = useState('')
  const [selectedRule, setSelectedRule] = useState('')
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [p, engs, dicts, availableRules] = await Promise.all([
          crackingApi.analyze(Number(artifactId)),
          engagementsApi.list().catch(() => []),
          crackingApi.dictionaries(),
          crackingApi.rules(),
        ])
        setPlan(p)
        setEngagements(engs)
        setDictionaries(dicts.filter(dictionary => !dictionary.compressed))
        setRules(availableRules)
        const rockyou = dicts.find(dictionary => !dictionary.compressed && dictionary.name.toLowerCase().includes('rockyou'))
        setSelectedDictionary(rockyou?.path ?? dicts.find(dictionary => !dictionary.compressed)?.path ?? '')
        const active = engs.find(e => e.status === 'ACTIVE')
        if (active) setSelectedEng(active.id)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [artifactId])

  async function handleCreateJob() {
    if (!selectedEng) {
      setError('Selecciona el engagement autorizado')
      return
    }
    const dictPath = customDictPath.trim() || selectedDictionary
    if (!dictPath) {
      setError('Selecciona un diccionario o escribe la ruta de uno personalizado')
      return
    }
    setCreating(true)
    setError(null)
    try {
      const job = await crackingApi.createJob(Number(artifactId), 'dictionary', selectedEng)
      await crackingApi.startJob(
        job.id,
        selectedEng,
        [dictPath],
        selectedRule ? [selectedRule] : undefined,
      )
      navigate('/cracking/' + job.id)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setCreating(false)
    }
  }

  function formatTime(seconds: number): string {
    if (seconds < 60) return seconds + 's'
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ' + (seconds % 60) + 's'
    return Math.floor(seconds / 3600) + 'h ' + Math.floor((seconds % 3600) / 60) + 'm'
  }

  if (loading) return <LoadingSpinner text="Analizando handshake..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>
  if (!plan) return <div className="callout callout-warning">No se pudo analizar el handshake</div>

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Analizar handshake #{artifactId}</h1>
          <div className="subtitle">Plan de cracking generado automáticamente</div>
        </div>
        <div className="detail-actions">
          <button className="btn btn-primary" disabled={creating} onClick={handleCreateJob}>
            {creating ? 'Iniciando...' : 'Crear e iniciar cracking'}
          </button>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}
      {plan.warnings?.length > 0 && (
        <div className="callout" style={{ borderLeft: '3px solid var(--yellow)' }}>
          {plan.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
        </div>
      )}

      {plan.hash_info && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header"><div className="card-title">Información del hash</div></div>
          <div className="detail-grid">
            <div className="detail-field">
              <div className="detail-label">BSSID</div>
              <div className="detail-value" style={{ fontFamily: 'monospace' }}>{plan.hash_info.bssid || '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">SSID</div>
              <div className="detail-value">{plan.hash_info.ssid || '—'}</div>
            </div>
            <div className="detail-field" style={{ gridColumn: '1 / -1' }}>
              <div className="detail-label">Hash .22000</div>
              <div className="detail-value" style={{ fontFamily: 'monospace', fontSize: 11, wordBreak: 'break-all' }}>{plan.hash_info.hash_line}</div>
            </div>
          </div>
        </div>
      )}

      <div className="form-group" style={{ maxWidth: 400 }}>
        <label className="form-label">Engagement para el job</label>
        <select className="form-select" value={selectedEng ?? ''} onChange={e => setSelectedEng(Number(e.target.value) || undefined)}>
          <option value="">Seleccionar engagement</option>
          {engagements.map(e => (
            <option key={e.id} value={e.id}>{e.code} — {e.name}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-2" style={{ maxWidth: 820 }}>
        <div className="form-group">
          <label className="form-label">Diccionario</label>
          <select className="form-select" value={selectedDictionary} onChange={e => setSelectedDictionary(e.target.value)}>
            <option value="">Seleccionar diccionario</option>
            {dictionaries.map(dictionary => (
              <option key={dictionary.path} value={dictionary.path}>{dictionary.name}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Ruta de diccionario personalizada (opcional)</label>
          <input
            className="form-input"
            type="text"
            value={customDictPath}
            onChange={e => setCustomDictPath(e.target.value)}
            placeholder={'/usr/share/wordlists/rockyou.txt o cualquier otra wordlist'}
            style={{ fontFamily: 'monospace', fontSize: 12 }}
          />
          <div className="subtitle" style={{ marginTop: 4 }}>
            Se usa en lugar de la selección anterior si está completa.
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Regla opcional</label>
          <select className="form-select" value={selectedRule} onChange={e => setSelectedRule(e.target.value)}>
            <option value="">Sin regla preferida</option>
            {rules.map(rule => <option key={rule.path} value={rule.path}>{rule.name}</option>)}
          </select>
        </div>
      </div>

      {plan.plan.stages?.length > 0 ? (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header"><div className="card-title">Plan de ataque ({plan.plan.stages.length} etapas)</div></div>
          <div className="table-container">
            <table>
              <thead><tr><th>#</th><th>Modo</th><th>Diccionario</th><th>Regla</th><th>Prioridad</th><th>Tiempo estimado</th></tr></thead>
              <tbody>
                {plan.plan.stages.map((s, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td><span className="badge">{s.mode}</span></td>
                    <td style={{ fontSize: 12, fontFamily: 'monospace' }}>{s.dictionary_path || '—'}</td>
                    <td style={{ fontSize: 12 }}>{s.rules_path || '—'}</td>
                    <td>{i + 1}</td>
                    <td style={{ fontSize: 12 }}>{formatTime(s.timeout_seconds ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>
            No se generaron etapas — no hay wordlists o reglas disponibles.
          </div>
        </div>
      )}
    </div>
  )
}
