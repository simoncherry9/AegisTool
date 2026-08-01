import { useState, useEffect } from 'react'
import { reportingApi } from '../../api/reporting'
import { api } from '../../api/client'
import { LoadingSpinner } from '../../components/LoadingSpinner'

export function ReportingPage() {
  const [engagements, setEngagements] = useState<any[]>([])
  const [reports, setReports] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // form state
  const [selectedEngagement, setSelectedEngagement] = useState('')
  const [format, setFormat] = useState('pdf')
  const [sections, setSections] = useState({
    executive: true,
    technical: true,
    evidence: true
  })
  const [generating, setGenerating] = useState(false)

  const loadData = async () => {
    try {
      const [engData, repData] = await Promise.all([
        api.get<any[]>('/engagements').catch(() => []),
        reportingApi.list().catch(() => [])
      ])
      setEngagements((engData || []) as any[])
      setReports((repData || []) as any[])
      if (engData && (engData as any[]).length > 0) setSelectedEngagement((engData as any[])[0].id)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    setGenerating(true)
    try {
      await reportingApi.generate({
        engagement_id: selectedEngagement,
        format,
        sections
      })
      await loadData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando reportes..." />

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Informes</h1>
          <div className="subtitle">Generación y descarga de reportes de auditoría</div>
        </div>
      </div>

      {error && <div className="callout callout-error">{error}</div>}

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">Generar Nuevo Reporte</div>
          </div>
          <form onSubmit={handleGenerate}>
            <div className="form-group">
              <label className="form-label">Engagement</label>
              <select className="form-select" value={selectedEngagement} onChange={(e) => setSelectedEngagement(e.target.value)}>
                {engagements.map(e => (
                  <option key={e.id} value={e.id}>{e.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Formato</label>
              <select className="form-select" value={format} onChange={(e) => setFormat(e.target.value)}>
                <option value="pdf">PDF (Profesional)</option>
                <option value="html">HTML (Interactivo)</option>
                <option value="json">JSON (Datos puros)</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Secciones a incluir</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={sections.executive} onChange={e => setSections({...sections, executive: e.target.checked})} />
                  Resumen Ejecutivo
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={sections.technical} onChange={e => setSections({...sections, technical: e.target.checked})} />
                  Detalles Técnicos (APs, Handshakes, Cracking)
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={sections.evidence} onChange={e => setSections({...sections, evidence: e.target.checked})} />
                  Evidencias
                </label>
              </div>
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={generating}>
              {generating ? 'Generando...' : '📄 Generar Reporte'}
            </button>
          </form>
        </div>

        <div className="card" style={{ padding: 0 }}>
          <div className="card-header" style={{ padding: '22px 22px 0' }}>
            <div className="card-title">Historial de Reportes</div>
          </div>
          {reports.length === 0 ? (
            <div className="empty-state">
              <p>No hay reportes generados.</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Formato</th>
                    <th>Estado</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map(r => (
                    <tr key={r.id}>
                      <td style={{ fontWeight: 600 }}>{r.name || `Reporte ${r.id.substring(0,6)}`}</td>
                      <td style={{ textTransform: 'uppercase', fontSize: 12, color: 'var(--text-muted)' }}>{r.format}</td>
                      <td>
                        {r.status === 'generating' ? (
                          <span className="badge badge-draft" style={{ animation: 'pulse 1.5s infinite' }}>Generando</span>
                        ) : (
                          <span className="badge badge-completed">Completado</span>
                        )}
                      </td>
                      <td>
                        {r.status === 'completed' && (
                          <button className="btn btn-sm btn-secondary" onClick={() => window.open(`/api/v1/reports/${r.id}/download`, '_blank')}>
                            Descargar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
