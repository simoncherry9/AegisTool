import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { evidenceApi, type CaptureDetail } from '../../api/evidence'

export function EvidenceDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [item, setItem] = useState<CaptureDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    evidenceApi.get(Number(id))
      .then(setItem)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  async function handleDelete() {
    if (!confirm('Eliminar esta evidencia permanentemente?')) return
    try {
      await evidenceApi.delete(Number(id))
      navigate('/evidence')
    } catch (e: any) {
      setError(e.message)
    }
  }

  if (loading) return <LoadingSpinner text="Cargando evidencia..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>
  if (!item) return <div className="callout callout-warning">Evidencia no encontrada</div>

  return (
    <div>
      <div className="detail-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1>Evidencia #{item.id}</h1>
            <span className="badge">{item.category}</span>
            <span className="badge">{item.format}</span>
          </div>
          <div className="subtitle">{item.original_filename || 'Sin nombre de archivo'}</div>
        </div>
        <div className="detail-actions">
          <a className="btn btn-primary" href={'/api/v1/evidence/' + item.id + '/download'}>📥 Descargar</a>
          <button className="btn btn-danger" onClick={handleDelete}>🗑 Eliminar</button>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header"><div className="card-title">Información del archivo</div></div>
          <div className="detail-grid">
            <div className="detail-field">
              <div className="detail-label">Archivo original</div>
              <div className="detail-value">{item.original_filename || '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Formato</div>
              <div className="detail-value">{item.format}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Tamaño</div>
              <div className="detail-value">{item.size_bytes ? (item.size_bytes / 1024 / 1024).toFixed(2) + ' MB' : '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">SHA256</div>
              <div className="detail-value" style={{ fontSize: 11, fontFamily: 'monospace', wordBreak: 'break-all' }}>{item.sha256 || '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Ruta</div>
              <div className="detail-value" style={{ fontSize: 11, fontFamily: 'monospace', wordBreak: 'break-all' }}>{item.path}</div>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">Contexto</div></div>
          <div className="detail-grid">
            <div className="detail-field">
              <div className="detail-label">Engagement</div>
              <div className="detail-value"><a href={'/engagements/' + item.engagement_id}>#{item.engagement_id}</a></div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Job</div>
              <div className="detail-value">{item.job_id ? '#' + item.job_id : '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Herramienta</div>
              <div className="detail-value">{item.tool || '—'}{item.tool_version ? ' v' + item.tool_version : ''}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Interfaz</div>
              <div className="detail-value">{item.interface || '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Canal</div>
              <div className="detail-value">{item.channel ?? '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">BSSID / SSID</div>
              <div className="detail-value" style={{ fontSize: 12 }}>{item.bssid || '—'}{item.ssid ? ' (' + item.ssid + ')' : ''}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Derivado de</div>
              <div className="detail-value">{item.derived_from_id ? '#' + item.derived_from_id : '—'}</div>
            </div>
            <div className="detail-field">
              <div className="detail-label">Creado</div>
              <div className="detail-value">{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
