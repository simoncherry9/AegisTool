export function LoadingSpinner({ text = 'Cargando...' }: { text?: string }) {
  return (
    <div className="loading-container">
      <div className="spinner" />
      <span>{text}</span>
    </div>
  )
}
