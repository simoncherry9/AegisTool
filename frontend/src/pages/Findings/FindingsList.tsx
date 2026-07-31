import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { StatusBadge } from '../../components/StatusBadge'
import { SeverityBadge } from '../../components/SeverityBadge'
import { findingsApi, type FindingRead, type FindingSummary } from '../../api/findings'
import { engagementsApi, type Engagement } from '../../api/engagements'

export function FindingsList() {
  const [findings, setFindings] = useState<FindingRead[]>([])
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [summary, setSummary] = useState<FindingSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [severity, setSeverity] = useState('')
  const [status, setStatus] = useState('')
  const [selectedEng, setSelectedEng] = useState<number | undefined>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    async function load() {
      try {
        const engs = await engagementsApi.list()
        setEngagements(engs)
        // Pre-select from URL query param, or fall back to active engagement
        const urlEngId = searchParams.get('engagement_id')
        if (urlEngId) {
          const parsed = Number(urlEngId)
          if (parsed && engs.some((e) => e.id === parsed)) {
            setSelectedEng(parsed)
            return
          }
        }
        const active = engs.find((e) => e.status === 'ACTIVE')
        if (active) {
          setSelectedEng(active.id)
        }
      } catch { /* ok */ }
    }
    load()
  }, [])

  useEffect(() => {
    async function loadFindings() {
      setLoading(true)
      try {
        const data = await findingsApi.list({
          engagement_id: selectedEng,
          severity: severity || undefined,
          status: status || undefined,
        })
        setFindings(data)
        if (selectedEng) {
          const s = await findingsApi.summary(selectedEng).catch(() => null)
          setSummary(s)
        }
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    loadFindings()
  }, [selectedEng, severity, status])

  async function handleRunEngine() {
    if (!selectedEng) return
    setLoading(true)
    try {
      await findingsApi.runEngine(selectedEng)
      const data = await findingsApi.list({ engagement_id: selectedEng })
      setFindings(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Hallazgos</h1>
          <div className="subtitle">Vulnerabilidades y observaciones documentadas</div>
        </div>
        <div className="detail-actions">
          <button className="btn btn-primary" onClick={handleRunEngine} disabled={!selectedEng}>
            Ejecutar motor
          </button>
        </div>
      </div>

      {summary && (
        <div className="grid grid-4" style={{ marginBottom: 24 }}>
          <div className="card stat-card">
            <div className="stat-value" style={{ color: 'var(--red)' }}>{summary.open_critical}</div>
            <div className="stat-label">Críticos</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value" style={{ color: 'var(--orange)' }}>{summary.open_high}</div>
            <div className="stat-label">Altos</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value" style={{ color: 'var(--yellow)' }}>{summary.open_medium}</div>
            <div className="stat-label">Medios</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value">{summary.total}</div>
            <div className="stat-label">Total</div>
          </div>
        </div>
      )}

      <div className="filters">
        <select className="form-select" value={selectedEng ?? ''} onChange={(e) => setSelectedEng(Number(e.target.value) || undefined)}>
          <option value="">Todos los engagements</option>
          {engagements.map((e) => (
            <option key={e.id} value={e.id}>{e.code} — {e.name}</option>
          ))}
        </select>
        <select className="form-select" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">Todas las severidades</option>
          <option value="CRITICAL">Crítico</option>
          <option value="HIGH">Alto</option>
          <option value="MEDIUM">Medio</option>
          <option value="LOW">Bajo</option>
          <option value="INFO">Info</option>
        </select>
        <select className="form-select" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todos los estados</option>
          <option value="OPEN">Abierto</option>
          <option value="CONFIRMED">Confirmado</option>
          <option value="REMEDIATED">Remediado</option>
          <option value="FALSE_POSITIVE">Falso positivo</option>
          <option value="ACCEPTED_RISK">Riesgo aceptado</option>
        </select>
      </div>

      {loading ? (
        <LoadingSpinner text="Cargando hallazgos..." />
      ) : error ? (
        <div className="callout callout-error">{error}</div>
      ) : findings.length === 0 ? (
        <EmptyState
          title="Sin hallazgos"
          description="Ejecuta el motor de hallazgos para generar hallazgos automáticos."
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>#</th><th>Título</th><th>Categoría</th><th>Severidad</th><th>Confianza</th><th>Estado</th><th>Regla</th></tr>
              </thead>
              <tbody>
                {findings.map((f) => (
                  <tr key={f.id} className="clickable" onClick={() => navigate(`/findings/${f.id}`)}>
                    <td>#{f.id}</td>
                    <td style={{ fontWeight: 500 }}>{f.title}</td>
                    <td style={{ fontSize: 12 }}>{f.category}</td>
                    <td><SeverityBadge severity={f.severity} /></td>
                    <td>{f.confidence != null ? `${(f.confidence * 100).toFixed(0)}%` : '—'}</td>
                    <td><StatusBadge status={f.status} /></td>
                    <td style={{ fontSize: 12, fontFamily: 'monospace' }}>{f.rule_id || '—'}</td>
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
