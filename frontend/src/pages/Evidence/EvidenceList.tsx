import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { evidenceApi, type CaptureListItem } from '../../api/evidence'

export function EvidenceList() {
  const [items, setItems] = useState<CaptureListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    evidenceApi.list({ limit: 200 })
      .then(setItems)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleDelete(id: number, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm('Eliminar esta evidencia?')) return
    try {
      await evidenceApi.delete(id)
      setItems(items.filter(i => i.id !== id))
    } catch (e: any) {
      setError(e.message)
    }
  }

  function formatSize(bytes: number | null): string {
    if (!bytes) return '—'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  if (loading) return <LoadingSpinner text="Cargando evidencia..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Evidencia</h1>
          <div className="subtitle">Capturas almacenadas y archivos de evidencia</div>
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="Sin evidencia"
          description="Las capturas de discovery y handshakes aparecerán aquí automáticamente."
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Archivo</th>
                  <th>Categoría</th>
                  <th>Formato</th>
                  <th>Tamaño</th>
                  <th>Herramienta</th>
                  <th>SHA256</th>
                  <th>Engagement</th>
                  <th>Fecha</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {items.map(ev => (
                  <tr key={ev.id} className="clickable" onClick={() => navigate('/evidence/' + ev.id)}>
                    <td>#{ev.id}</td>
                    <td style={{ fontWeight: 500, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ev.original_filename || '—'}
                    </td>
                    <td><span className="badge">{ev.category}</span></td>
                    <td style={{ fontSize: 12, fontFamily: 'monospace' }}>{ev.format}</td>
                    <td style={{ fontSize: 12 }}>{formatSize(ev.size_bytes)}</td>
                    <td style={{ fontSize: 12 }}>{ev.tool || '—'}</td>
                    <td style={{ fontSize: 10, fontFamily: 'monospace', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {ev.sha256 ? ev.sha256.substring(0, 12) + '…' : '—'}
                    </td>
                    <td><a href={'/engagements/' + ev.engagement_id} style={{ fontSize: 12 }}>#{ev.engagement_id}</a></td>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {ev.created_at ? new Date(ev.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <a className="btn btn-sm btn-secondary" href={'/api/v1/evidence/' + ev.id + '/download'}
                          style={{ fontSize: 10, padding: '2px 8px' }}>📥</a>
                        <button className="btn btn-sm btn-danger"
                          style={{ fontSize: 10, padding: '2px 8px' }}
                          onClick={(e) => handleDelete(ev.id, e)}>🗑</button>
                      </div>
                    </td>
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
