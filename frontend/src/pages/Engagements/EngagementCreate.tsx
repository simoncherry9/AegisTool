import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { engagementsApi } from '../../api/engagements'
import { usersApi, User } from '../../api/users'

export function EngagementCreate() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [client, setClient] = useState('')
  const [operator, setOperator] = useState('')
  const [operatorId, setOperatorId] = useState<number | undefined>(undefined)
  const [usersList, setUsersList] = useState<User[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    usersApi.list().then((users) => {
      setUsersList(users)
      if (users.length > 0) {
        setOperatorId(users[0].id)
        setOperator(users[0].full_name || users[0].username)
      }
    }).catch(() => {})
  }, [])

  const handleOperatorSelect = (userIdStr: string) => {
    if (!userIdStr) {
      setOperatorId(undefined)
      setOperator('')
      return
    }
    const selectedId = Number(userIdStr)
    const selectedUser = usersList.find((u) => u.id === selectedId)
    if (selectedUser) {
      setOperatorId(selectedUser.id)
      setOperator(selectedUser.full_name || selectedUser.username)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim() || !client.trim() || !operator.trim()) {
      setError('Todos los campos son obligatorios')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const eng = await engagementsApi.create({
        name,
        client,
        operator,
        operator_id: operatorId,
      } as any)
      navigate(`/engagements/${eng.id}`)
    } catch (e: any) {
      const raw = e.message || ''
      if (raw.includes('IntegrityError') || raw.includes('NOT NULL') || raw.includes('constraint failed')) {
        setError('Error interno del servidor. Reintenta o revisa la consola del backend.')
      } else if (raw.includes('500')) {
        setError('Error interno del servidor. Revisa los logs del backend.')
      } else if (raw.includes('Failed to fetch') || raw.includes('NetworkError')) {
        setError('No se puede conectar con el backend. Verifica que el servidor esté corriendo.')
      } else {
        const short = raw.length > 120 ? raw.substring(0, 120) + '...' : raw
        setError(short)
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 560 }}>
      <div className="detail-header">
        <div>
          <h1>Nuevo engagement</h1>
          <div className="subtitle">Crear una nueva auditoría</div>
        </div>
      </div>

      <div className="card">
        {error && <div className="callout callout-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Nombre</label>
            <input className="form-input" value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Ej: Auditoría Q1 2026" required />
          </div>
          <div className="form-group">
            <label className="form-label">Cliente</label>
            <input className="form-input" value={client} onChange={(e) => setClient(e.target.value)}
              placeholder="Nombre del cliente" required />
          </div>
          <div className="form-group">
            <label className="form-label">Encargado del Engagement (Operador)</label>
            {usersList.length > 0 ? (
              <select
                className="form-input"
                value={operatorId || ''}
                onChange={(e) => handleOperatorSelect(e.target.value)}
                required
              >
                {usersList.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} ({u.username}) — {u.role}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="form-input"
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                placeholder="Nombre o email del operador"
                required
              />
            )}
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 24 }}>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Creando...' : 'Crear engagement'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/engagements')}>
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
