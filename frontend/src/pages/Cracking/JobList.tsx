import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LoadingSpinner } from '../../components/LoadingSpinner'
import { EmptyState } from '../../components/EmptyState'
import { StatusBadge } from '../../components/StatusBadge'
import { crackingApi, type CrackingJob, type DictionaryInfo, type RuleInfo } from '../../api/cracking'

export function JobList() {
  const [jobs, setJobs] = useState<CrackingJob[]>([])
  const [dicts, setDicts] = useState<DictionaryInfo[]>([])
  const [rules, setRules] = useState<RuleInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      try {
        const [jobsData, dictsData, rulesData] = await Promise.all([
          crackingApi.jobs(),
          crackingApi.dictionaries().catch(() => []),
          crackingApi.rules().catch(() => []),
        ])
        setJobs(jobsData)
        setDicts(dictsData)
        setRules(rulesData)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <LoadingSpinner text="Cargando trabajos de cracking..." />
  if (error) return <div className="callout callout-error">Error: {error}</div>

  const filtered = statusFilter ? jobs.filter((j) => j.status === statusFilter) : jobs

  return (
    <div>
      <div className="detail-header">
        <div>
          <h1>Cracking</h1>
          <div className="subtitle">Trabajos de recuperación de contraseñas WPA2</div>
        </div>
      </div>

      {/* Info cards */}
      <div className="grid grid-2" style={{ marginBottom: 24 }}>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: 'var(--accent)', fontSize: 20 }}>{dicts.length}</div>
          <div className="stat-label">Wordlists disponibles</div>
          {dicts.slice(0, 3).map((d) => (
            <div key={d.name} style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {d.name} ({(d.size_bytes / 1024 / 1024).toFixed(0)} MB)
            </div>
          ))}
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: 'var(--yellow)', fontSize: 20 }}>{rules.length}</div>
          <div className="stat-label">Reglas disponibles</div>
          {rules.slice(0, 3).map((r) => (
            <div key={r.name} style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {r.name} ({r.rule_count ?? '?'} reglas)
            </div>
          ))}
        </div>
      </div>

      <div className="filters">
        <select className="form-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">Todos los estados</option>
          <option value="CREATED">Creados</option>
          <option value="QUEUED">En cola</option>
          <option value="RUNNING">Ejecutando</option>
          <option value="RECOVERED">Recuperados</option>
          <option value="EXHAUSTED">Agotados</option>
          <option value="FAILED">Fallidos</option>
          <option value="CANCELLED">Cancelados</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title="Sin trabajos de cracking"
          description="Los trabajos de cracking aparecerán aquí cuando se creen desde la API o CLI."
        />
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table>
              <thead>
                <tr><th>#</th><th>Estrategia</th><th>Estado</th><th>Progreso</th><th>Velocidad</th><th>Recuperada</th><th>Inicio</th></tr>
              </thead>
              <tbody>
                {filtered.map((j) => (
                  <tr key={j.id} className="clickable" onClick={() => navigate(`/cracking/${j.id}`)}>
                    <td><Link to={`/cracking/${j.id}`} style={{ fontWeight: 600 }}>#{j.id}</Link></td>
                    <td style={{ fontSize: 12 }}>{j.strategy}</td>
                    <td><StatusBadge status={j.status} /></td>
                    <td>{j.progress != null ? `${(j.progress * 100).toFixed(0)}%` : '—'}</td>
                    <td style={{ fontSize: 12 }}>{j.speed ? `${(j.speed / 1000).toFixed(0)}k H/s` : '—'}</td>
                    <td>{j.recovered ? <span style={{ color: 'var(--green)', fontWeight: 600 }}>✓</span> : '—'}</td>
                    <td style={{ fontSize: 12 }}>{j.started_at ? new Date(j.started_at).toLocaleString() : '—'}</td>
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
