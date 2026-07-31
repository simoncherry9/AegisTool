import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { findingsApi, type FindingRule } from '../../api/findings'
import { engagementsApi, type Engagement } from '../../api/engagements'

const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
const CATEGORIES = [
  'weak-crypto', 'no-encryption', 'wps-enabled', 'pmf-disabled',
  'wep-enabled', 'weak-password', 'downgrade', 'info-disclosure',
  'misconfiguration', 'other',
]

export function FindingsCreatePage() {
  const navigate = useNavigate()
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [rules, setRules] = useState<FindingRule[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [engagementId, setEngagementId] = useState<number | undefined>()
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('weak-crypto')
  const [severity, setSeverity] = useState('MEDIUM')
  const [description, setDescription] = useState('')
  const [impact, setImpact] = useState('')
  const [remediation, setRemediation] = useState('')
  const [affectedAssets, setAffectedAssets] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const [engs, rs] = await Promise.all([
          engagementsApi.list(),
          findingsApi.rules().catch(() => []),
        ])
        setEngagements(engs)
        setRules(rs)
        const active = engs.find(e => e.status === 'ACTIVE')
        if (active) setEngagementId(active.id)
      } catch { /* ok */ }
      finally { setLoading(false) }
    }
    load()
  }, [])

  function applyRule(rule: FindingRule) {
    setTitle(rule.title)
    setCategory(rule.category)
    setSeverity(rule.severity)
    setDescription(rule.description || '')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!engagementId || !title.trim()) {
      setError('Engagement y título son obligatorios')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const finding = await findingsApi.create({
        engagement_id: engagementId,
        title: title.trim(),
        category,
        severity,
        description: description || undefined,
        impact: impact || undefined,
        remediation: remediation || undefined,
        affected_assets: affectedAssets ? affectedAssets.split('\n').map(s => s.trim()).filter(Boolean) : undefined,
      })
      navigate('/findings/' + finding.id)
    } catch (e: any) {
      setError(e.message || 'Error al crear hallazgo')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando..." />

  return (
    <div style={{ maxWidth: 700 }}>
      <div className="detail-header">
        <div>
          <h1>Nuevo hallazgo</h1>
          <div className="subtitle">Crear hallazgo manualmente</div>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}

      {rules.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header"><div className="card-title">Plantillas de reglas</div></div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '0 20px 16px' }}>
            {rules.map(r => (
              <button key={r.rule_id} className="btn btn-sm btn-secondary"
                onClick={() => applyRule(r)} style={{ fontSize: 11 }}>
                {r.title}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Engagement</label>
            <select className="form-select" value={engagementId ?? ''}
              onChange={e => setEngagementId(Number(e.target.value) || undefined)} required>
              <option value="">Seleccionar engagement</option>
              {engagements.map(e => (
                <option key={e.id} value={e.id}>{e.code} — {e.name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Título</label>
            <input className="form-input" value={title} onChange={e => setTitle(e.target.value)} required />
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Categoría</label>
              <select className="form-select" value={category} onChange={e => setCategory(e.target.value)}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Severidad</label>
              <select className="form-select" value={severity} onChange={e => setSeverity(e.target.value)}>
                {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Descripción</label>
            <textarea className="form-input" rows={3} value={description} onChange={e => setDescription(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Impacto</label>
            <textarea className="form-input" rows={2} value={impact} onChange={e => setImpact(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Remediación</label>
            <textarea className="form-input" rows={2} value={remediation} onChange={e => setRemediation(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Assets afectados (uno por línea)</label>
            <textarea className="form-input" rows={2} value={affectedAssets} onChange={e => setAffectedAssets(e.target.value)}
              placeholder="BSSID: XX:XX:XX:XX:XX:XX&#10;SSID: MiRed" />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 24 }}>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Creando...' : 'Crear hallazgo'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/findings')}>Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  )
}
