import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { StatusBadge } from '../../components/StatusBadge'
import { engagementsApi, type Engagement } from '../../api/engagements'
import { findingsApi, type FindingRead, type FindingSummary } from '../../api/findings'
import { crackingApi, type CrackingJob } from '../../api/cracking'
import { discoveryApi, type AccessPoint } from '../../api/discovery'
import { validationApi, type HandshakeReport } from '../../api/validation'

interface DetailData {
  engagement: Engagement
  findings: FindingRead[]
  summary: FindingSummary | null
  crackingJobs: CrackingJob[]
  accessPoints: AccessPoint[]
  handshakes: HandshakeReport[]
}

type StageStatus = 'pending' | 'active' | 'completed' | 'skipped'

interface WorkflowStage {
  key: string
  label: string
  description: string
  icon: string
  status: StageStatus
  link: string
  buttonLabel: string
  count?: number
}

export function EngagementDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<DetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activating, setActivating] = useState(false)
  const [closing, setClosing] = useState(false)

  const engagementId = Number(id)

  useEffect(() => {
    async function load() {
      try {
        const [engagement, findings, summary, crackingJobs, aps, handshakes] = await Promise.all([
          engagementsApi.get(engagementId),
          findingsApi.list({ engagement_id: engagementId }).catch(() => []),
          findingsApi.summary(engagementId).catch(() => null),
          crackingApi.jobs(engagementId).catch(() => []),
          discoveryApi.accessPoints({ limit: 200 }).catch(() => []),
          validationApi.artifacts({}).catch(() => []),
        ])
        setData({ engagement, findings, summary, crackingJobs, accessPoints: aps, handshakes })
      } catch (e: any) {
        const raw = e.message || ''
        if (raw.includes('Failed to fetch') || raw.includes('NetworkError')) {
          setError('No se puede conectar con el backend. Verifica que el servidor esté corriendo.')
        } else {
          setError(raw.length > 200 ? raw.substring(0, 200) + '...' : raw)
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [engagementId])

  async function handleActivate() {
    if (!data) return
    setActivating(true)
    try {
      const updated = await engagementsApi.activate(data.engagement.id)
      setData({ ...data, engagement: updated })
    } catch (e: any) {
      const raw = e.message || ''
      setError(raw.length > 200 ? raw.substring(0, 200) + '...' : raw)
    } finally {
      setActivating(false)
    }
  }

  async function handleClose() {
    if (!data || !confirm('Cerrar engagement ' + data.engagement.code + '? Esta acción no se puede deshacer.')) return
    setClosing(true)
    try {
      const updated = await engagementsApi.close(data.engagement.id)
      setData({ ...data, engagement: updated })
    } catch (e: any) {
      const raw = e.message || ''
      setError(raw.length > 200 ? raw.substring(0, 200) + '...' : raw)
    } finally {
      setClosing(false)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando engagement..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>
  if (!data) return <div className="callout callout-warning">Engagement no encontrado</div>

  const { engagement, findings, summary, crackingJobs, accessPoints, handshakes } = data
  const isActive = engagement.status === 'ACTIVE'

  // Determinar estado de cada etapa
  const hasDiscovery = accessPoints.length > 0
  const hasHandshakes = handshakes.filter(h => h.validated).length > 0
  const hasCracking = crackingJobs.length > 0
  const hasFindings = findings.length > 0

  const stages: WorkflowStage[] = [
    {
      key: 'activate',
      label: '1. Activar',
      description: 'Habilitar el engagement para comenzar la auditoría',
      icon: isActive ? '✓' : '🔒',
      status: isActive ? 'completed' : 'active',
      link: '',
      buttonLabel: isActive ? 'Activado' : 'Activar engagement',
    },
    {
      key: 'discovery',
      label: '2. Descubrimiento',
      description: 'Escanear redes y detectar puntos de acceso',
      icon: '📡',
      status: hasDiscovery ? 'completed' : (isActive ? 'active' : 'pending'),
      link: '/discovery',
      buttonLabel: hasDiscovery ? `${accessPoints.length} redes detectadas` : 'Ir a Discovery',
      count: accessPoints.length,
    },
    {
      key: 'handshakes',
      label: '3. Captura y validación',
      description: 'Capturar handshakes y PMKID, validar calidad',
      icon: '🔑',
      status: hasHandshakes ? 'completed' : (hasDiscovery ? 'active' : 'pending'),
      link: '/handshakes',
      buttonLabel: hasHandshakes ? `${handshakes.filter(h => h.validated).length} validados` : 'Ir a Handshakes',
      count: handshakes.filter(h => h.validated).length,
    },
    {
      key: 'cracking',
      label: '4. Cracking',
      description: 'Ejecutar ataques de diccionario y fuerza bruta',
      icon: '⚡',
      status: hasCracking ? 'completed' : (hasHandshakes ? 'active' : 'pending'),
      link: '/cracking',
      buttonLabel: hasCracking ? `${crackingJobs.length} trabajos` : 'Ir a Cracking',
      count: crackingJobs.length,
    },
    {
      key: 'findings',
      label: '5. Hallazgos',
      description: 'Revisar resultados y generar reportes',
      icon: '📋',
      status: hasFindings ? 'completed' : (hasCracking ? 'active' : 'pending'),
      link: '/findings',
      buttonLabel: hasFindings ? `${findings.length} hallazgos` : 'Ir a Hallazgos',
      count: findings.length,
    },
  ]

  // Determinar siguiente acción
  const nextStage = stages.find(s => s.status === 'active')
  const nextAction = nextStage || stages[stages.length - 1]

  return (
    <div>
      {/* Header */}
      <div className="detail-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1>{engagement.code}: {engagement.name}</h1>
            <StatusBadge status={engagement.status} />
          </div>
          <div className="subtitle" style={{ marginTop: 4 }}>
            {engagement.client} — {engagement.operator}
            {engagement.created_at && ` — Creado ${new Date(engagement.created_at).toLocaleDateString()}`}
          </div>
        </div>
        <div className="detail-actions">
          {isActive && (
            <button className="btn btn-danger" disabled={closing} onClick={handleClose}>
              {closing ? 'Cerrando...' : 'Cerrar engagement'}
            </button>
          )}
        </div>
      </div>

      {/* Workflow pipeline */}
      <div className="card" style={{ marginBottom: 24, padding: '24px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ margin: 0 }}>Pipeline de auditoría</h3>
          {!isActive && (
            <button className="btn btn-primary" disabled={activating} onClick={handleActivate}
              style={{ fontSize: 15, padding: '10px 24px' }}>
              {activating ? 'Activando...' : '🔓 Activar engagement'}
            </button>
          )}
        </div>

        {/* Pipeline visual */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'stretch', flexWrap: 'wrap' }}>
          {stages.map((stage, i) => {
            const isNext = stage.key === nextAction?.key
            const isLast = i === stages.length - 1
            const done = stage.status === 'completed'

            return (
              <div key={stage.key} style={{
                flex: '1 1 160px',
                minWidth: 140,
                opacity: stage.status === 'pending' ? 0.4 : 1,
              }}>
                <div style={{
                  background: done ? 'rgba(102, 187, 106, 0.1)' : (isNext ? 'rgba(79, 195, 247, 0.1)' : 'var(--bg-card)'),
                  border: `2px solid ${
                    done ? 'var(--green)' : isNext ? 'var(--accent)' : 'var(--border)'
                  }`,
                  borderRadius: 12,
                  padding: '14px 12px',
                  textAlign: 'center',
                  position: 'relative',
                }}>
                  <div style={{ fontSize: 24, marginBottom: 6 }}>{stage.icon}</div>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2 }}>{stage.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>{stage.description}</div>
                  {done && <div style={{ color: 'var(--green)', fontSize: 11, fontWeight: 600 }}>✓ Completo</div>}
                  {isNext && !done && (
                    stage.key === 'activate' ? (
                      <button className="btn btn-primary" disabled={activating} onClick={handleActivate}
                        style={{ fontSize: 11, padding: '4px 12px', marginTop: 4 }}>
                        {activating ? '...' : 'Activar'}
                      </button>
                    ) : (
                      <Link to={stage.link} className="btn btn-primary"
                        style={{ fontSize: 11, padding: '4px 12px', marginTop: 4, display: 'inline-block' }}>
                        Comenzar
                      </Link>
                    )
                  )}
                  {stage.count !== undefined && stage.count > 0 && (
                    <div style={{
                      position: 'absolute', top: -8, right: -8,
                      background: done ? 'var(--green)' : 'var(--accent)',
                      color: '#fff', borderRadius: 10, padding: '0 8px',
                      fontSize: 11, fontWeight: 700, lineHeight: '20px',
                    }}>{stage.count}</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Quick actions row */}
        {isActive && (
          <div style={{
            display: 'flex', gap: 10, marginTop: 20, paddingTop: 16,
            borderTop: '1px solid var(--border)', flexWrap: 'wrap',
          }}>
            <span style={{ fontSize: 13, color: 'var(--text-muted)', alignSelf: 'center' }}>
              Acciones rápidas:
            </span>
            <Link to="/discovery" className="btn btn-sm btn-secondary">📡 Discovery</Link>
            <Link to="/handshakes" className="btn btn-sm btn-secondary">🔑 Handshakes</Link>
            <Link to="/cracking" className="btn btn-sm btn-secondary">⚡ Cracking</Link>
            <Link to={`/findings?engagement_id=${engagement.id}`} className="btn btn-sm btn-secondary">📋 Hallazgos</Link>
          </div>
        )}
      </div>

      {/* Stats grid */}
      <div className="grid grid-4" style={{ marginBottom: 24 }}>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: 'var(--accent)' }}>{accessPoints.length}</div>
          <div className="stat-label">Redes detectadas</div>
          <div className="stat-trend up">{hasDiscovery ? 'Discovery completado' : 'Pendiente'}</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: hasHandshakes ? 'var(--green)' : 'var(--text-muted)' }}>
            {handshakes.filter(h => h.validated).length}
          </div>
          <div className="stat-label">Handshakes validados</div>
          <div className="stat-trend">{hasHandshakes ? 'Capturas realizadas' : 'Sin capturas'}</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: hasCracking ? 'var(--yellow)' : 'var(--text-muted)' }}>
            {crackingJobs.filter(j => j.recovered).length}/{crackingJobs.length}
          </div>
          <div className="stat-label">Contraseñas recuperadas</div>
          <div className="stat-trend">{crackingJobs.filter(j => j.status === 'RUNNING').length} activos</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: hasFindings ? 'var(--red)' : 'var(--text-muted)' }}>
            {summary?.open_critical ?? 0}/{findings.length}
          </div>
          <div className="stat-label">Hallazgos críticos</div>
          <div className="stat-trend">{hasFindings ? 'Revisar hallazgos' : 'Sin hallazgos'}</div>
        </div>
      </div>

      {/* Información del engagement */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Información del engagement</div>
          </div>
        </div>
        <div className="detail-grid">
          <div className="detail-field">
            <div className="detail-label">Código</div>
            <div className="detail-value" style={{ fontFamily: 'monospace' }}>{engagement.code}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Cliente</div>
            <div className="detail-value">{engagement.client}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Operador</div>
            <div className="detail-value">{engagement.operator}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Estado</div>
            <div className="detail-value"><StatusBadge status={engagement.status} /></div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Creado</div>
            <div className="detail-value">{engagement.created_at ? new Date(engagement.created_at).toLocaleString() : '—'}</div>
          </div>
          <div className="detail-field">
            <div className="detail-label">Inicio</div>
            <div className="detail-value">{engagement.start_date ? new Date(engagement.start_date).toLocaleDateString() : '—'}</div>
          </div>
        </div>
      </div>

      {/* Findings summary if they exist */}
      {summary && hasFindings && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Resumen de hallazgos</div>
            </div>
            <Link to={`/findings?engagement_id=${engagement.id}`} className="btn btn-sm btn-secondary">Ver todos</Link>
          </div>
          <div className="grid grid-3" style={{ marginTop: 8 }}>
            <div className="stat-card" style={{ borderLeft: '3px solid var(--red)', padding: '8px 12px' }}>
              <div className="stat-value" style={{ color: 'var(--red)', fontSize: 18 }}>{summary.open_critical}</div>
              <div className="stat-label" style={{ fontSize: 12 }}>Críticos</div>
            </div>
            <div className="stat-card" style={{ borderLeft: '3px solid var(--orange)', padding: '8px 12px' }}>
              <div className="stat-value" style={{ color: 'var(--orange)', fontSize: 18 }}>{summary.open_high}</div>
              <div className="stat-label" style={{ fontSize: 12 }}>Altos</div>
            </div>
            <div className="stat-card" style={{ borderLeft: '3px solid var(--yellow)', padding: '8px 12px' }}>
              <div className="stat-value" style={{ color: 'var(--yellow)', fontSize: 18 }}>{summary.open_medium}</div>
              <div className="stat-label" style={{ fontSize: 12 }}>Medios</div>
            </div>
          </div>
        </div>
      )}

      {/* Últimos resultados */}
      {hasCracking && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Últimos trabajos de cracking</div>
            </div>
            <Link to={`/cracking`} className="btn btn-sm btn-secondary">Ver todos</Link>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>#</th><th>Estrategia</th><th>Estado</th><th>Progreso</th><th>Recuperada</th></tr>
              </thead>
              <tbody>
                {crackingJobs.slice(0, 5).map((j) => (
                  <tr key={j.id} className="clickable" onClick={() => navigate(`/cracking/${j.id}`)}>
                    <td>#{j.id}</td>
                    <td>{j.strategy}</td>
                    <td><StatusBadge status={j.status} /></td>
                    <td>{j.progress != null ? `${(j.progress * 100).toFixed(0)}%` : '—'}</td>
                    <td>{j.recovered ? '✓' : '—'}</td>
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
