interface SeverityBadgeProps {
  severity: string
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const sev = severity.toUpperCase()
  const cls = sev === 'CRITICAL' ? 'badge-critical'
    : sev === 'HIGH' ? 'badge-high'
    : sev === 'MEDIUM' ? 'badge-medium'
    : sev === 'LOW' ? 'badge-low'
    : 'badge-info'
  return <span className={`badge ${cls}`}>{sev}</span>
}
