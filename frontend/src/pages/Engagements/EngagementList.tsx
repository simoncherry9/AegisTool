import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { StatusBadge } from '../../components/StatusBadge'
import { engagementsApi, type Engagement } from '../../api/engagements'

export function EngagementList() {
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    engagementsApi.list()
      .then(setEngagements)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner text="Cargando engagements..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Engagements</h1>
          <div className="subtitle">Auditorías registradas en el sistema</div>
        </div>
        <div className="detail-actions">
          <button className="btn btn-primary" onClick={() => navigate('/engagements/new')}>
            + Nuevo engagement
          </button>
        </div>
      </div>

      {engagements.length === 0 ? (
        <EmptyState
          title="Sin engagements"
          description="Crea tu primer engagement para comenzar una auditoría."
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Nombre</th>
                  <th>Cliente</th>
                  <th>Operador</th>
                  <th>Estado</th>
                  <th>Inicio</th>
                  <th>Fin</th>
                </tr>
              </thead>
              <tbody>
                {engagements.map((e) => (
                  <tr key={e.id} className="clickable" onClick={() => navigate(`/engagements/${e.id}`)}>
                    <td><Link to={`/engagements/${e.id}`} style={{ fontWeight: 600 }}>{e.code}</Link></td>
                    <td>{e.name}</td>
                    <td>{e.client}</td>
                    <td>{e.operator}</td>
                    <td><StatusBadge status={e.status} /></td>
                    <td>{e.start_date ? new Date(e.start_date).toLocaleDateString() : '—'}</td>
                    <td>{e.end_date ? new Date(e.end_date).toLocaleDateString() : '—'}</td>
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
