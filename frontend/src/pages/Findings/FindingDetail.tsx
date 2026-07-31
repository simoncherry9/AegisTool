import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { StatusBadge } from '../../components/StatusBadge'
import { SeverityBadge } from '../../components/SeverityBadge'
import { findingsApi, type FindingRead } from '../../api/findings'

export function FindingDetail() {
  const { id } = useParams<{ id: string }>()
  const [finding, setFinding] = useState<FindingRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    findingsApi.get(Number(id))
      .then(setFinding)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  async function handleStatusChange(newStatus: string) {
    if (!finding) return
    try {
      const updated = await findingsApi.update(finding.id, { status: newStatus })
      setFinding(updated)
    } catch (e: any) {
      setError(e.message)
    }
  }

  async function handleDelete() {
    if (!finding || !confirm('¿Eliminar este hallazgo?')) return
    try {
      await findingsApi.delete(finding.id)
      navigate('/findings')
    } catch (e: any) {
      setError(e.message)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando hallazgo..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>
  if (!finding) return <div className="callout callout-warning">Hallazgo no encontrado</div>

  return (
    <div>
      <div className="detail-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
            <h1 style={{ fontSize: 22 }}>{finding.title}</h1>
            <SeverityBadge severity={finding.severity} />
            <StatusBadge status={finding.status} />
          </div>
          <div className="subtitle">
            #{finding.id} · {finding.category}
            {finding.rule_id && <> · <span style={{ fontFamily: 'monospace' }}>{finding.rule_id}</span></>}
          </div>
        </div>
        <div className="detail-actions">
          <select className="form-select" style={{ width: 'auto' }} value="" onChange={(e) => e.target.value && handleStatusChange(e.target.value)}>
            <option value="">Cambiar estado...</option>
            <option value="CONFIRMED">Confirmar</option>
            <option value="REMEDIATED">Marcar remediado</option>
            <option value="FALSE_POSITIVE">Falso positivo</option>
            <option value="ACCEPTED_RISK">Riesgo aceptado</option>
          </select>
          <button className="btn btn-danger btn-sm" onClick={handleDelete}>Eliminar</button>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="detail-field" style={{ marginBottom: 12 }}>
            <div className="detail-label">Severidad</div>
            <div className="detail-value"><SeverityBadge severity={finding.severity} /></div>
          </div>
          <div className="detail-field" style={{ marginBottom: 12 }}>
            <div className="detail-label">Confianza</div>
            <div className="detail-value">{finding.confidence != null ? `${(finding.confidence * 100).toFixed(0)}%` : '—'}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Regla</div>
            <div className="detail-value" style={{ fontFamily: 'monospace', fontSize: 12 }}>{finding.rule_id || '—'}</div>
          </div>
        </div>
        <div className="card">
          <div className="detail-field" style={{ marginBottom: 12 }}>
            <div className="detail-label">Estado</div>
            <div className="detail-value"><StatusBadge status={finding.status} /></div>
          </div>
          <div className="detail-field" style={{ marginBottom: 12 }}>
            <div className="detail-label">Creado</div>
            <div className="detail-value">{finding.created_at ? new Date(finding.created_at).toLocaleString() : '—'}</div>
          </div>
          {finding.affected_assets.length > 0 && (
            <div className="detail-field">
              <div className="detail-label">Activos afectados</div>
              <div className="detail-value" style={{ fontFamily: 'monospace', fontSize: 12 }}>
                {finding.affected_assets.join(', ')}
              </div>
            </div>
          )}
        </div>
      </div>

      {finding.description && (
        <div className="detail-section">
          <h3>Descripción</h3>
          <div className="card">
            <p style={{ lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{finding.description}</p>
          </div>
        </div>
      )}

      {finding.impact && (
        <div className="detail-section">
          <h3>Impacto</h3>
          <div className="card">
            <p style={{ lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{finding.impact}</p>
          </div>
        </div>
      )}

      {finding.remediation && (
        <div className="detail-section">
          <h3>Remediación</h3>
          <div className="callout callout-success" style={{ whiteSpace: 'pre-wrap' }}>
            {finding.remediation}
          </div>
        </div>
      )}

      {Object.keys(finding.evidence).length > 0 && (
        <div className="detail-section">
          <h3>Evidencia</h3>
          <div className="card">
            <pre style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
              {JSON.stringify(finding.evidence, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
