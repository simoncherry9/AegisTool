import React, { useEffect, useState } from 'react'
import { usersApi, User, UserCreatePayload } from '../../api/users'
import { useAuth } from '../../context/AuthContext'

export const UsersList: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const { user: currentUser } = useAuth()

  const [form, setForm] = useState<UserCreatePayload>({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'OPERATOR',
  })
  const [modalError, setModalError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const loadUsers = async () => {
    try {
      setLoading(true)
      const data = await usersApi.list()
      setUsers(data)
    } catch (err: any) {
      setError(err.message || 'Error al cargar lista de usuarios')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setModalError(null)
    setSaving(true)

    try {
      await usersApi.create(form)
      setShowModal(false)
      setForm({ username: '', email: '', full_name: '', password: '', role: 'OPERATOR' })
      loadUsers()
    } catch (err: any) {
      setModalError(err.message || 'Error al crear usuario')
    } finally {
      setSaving(false)
    }
  }

  const handleToggleStatus = async (targetUser: User) => {
    try {
      await usersApi.update(targetUser.id, { is_active: !targetUser.is_active })
      loadUsers()
    } catch (err: any) {
      alert(err.message || 'Error al modificar estado')
    }
  }

  return (
    <div className="page-container">
      <div className="page-header flex-between">
        <div>
          <h1 className="page-title">Gestión de Usuarios y Operadores</h1>
          <p className="page-subtitle">
            Administración de cuentas, roles y encargados autorizados para engagements.
          </p>
        </div>
        {currentUser?.role === 'ADMIN' && (
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Nuevo Usuario
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        {loading ? (
          <div className="loading-state">Cargando usuarios...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Usuario</th>
                <th>Nombre Completo</th>
                <th>Email</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Registrado</th>
                {currentUser?.role === 'ADMIN' && <th>Acciones</th>}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>#{u.id}</td>
                  <td className="font-mono font-bold">{u.username}</td>
                  <td>{u.full_name}</td>
                  <td>{u.email}</td>
                  <td>
                    <span className={`badge badge-role-${u.role.toLowerCase()}`}>
                      {u.role}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill ${u.is_active ? 'active' : 'inactive'}`}>
                      {u.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                  {currentUser?.role === 'ADMIN' && (
                    <td>
                      <button
                        className={`btn-sm ${u.is_active ? 'btn-danger' : 'btn-success'}`}
                        onClick={() => handleToggleStatus(u)}
                        disabled={u.id === currentUser.id}
                      >
                        {u.is_active ? 'Desactivar' : 'Activar'}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h2>Crear Nuevo Usuario / Operador</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            {modalError && <div className="alert alert-error">{modalError}</div>}
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>Nombre de Usuario</label>
                <input
                  type="text"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  placeholder="ej. operador1"
                  required
                />
              </div>
              <div className="form-group">
                <label>Nombre Completo</label>
                <input
                  type="text"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  placeholder="ej. Carlos Auditor"
                  required
                />
              </div>
              <div className="form-group">
                <label>Correo Electrónico</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="ej. carlos@empresa.com"
                  required
                />
              </div>
              <div className="form-group">
                <label>Contraseña</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="Mínimo 6 caracteres"
                  required
                />
              </div>
              <div className="form-group">
                <label>Rol de Usuario</label>
                <select
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value as any })}
                >
                  <option value="OPERATOR">OPERATOR (Auditor de Campo)</option>
                  <option value="ADMIN">ADMIN (Administrador Completo)</option>
                  <option value="AUDITOR">AUDITOR (Solo Lectura / Reportes)</option>
                </select>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Guardando...' : 'Crear Usuario'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
