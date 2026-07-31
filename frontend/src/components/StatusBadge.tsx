interface StatusBadgeProps {
  status: string
}

const STATUS_CLASSES: Record<string, string> = {
  DRAFT: 'badge-draft',
  ACTIVE: 'badge-active',
  COMPLETED: 'badge-completed',
  CANCELLED: 'badge-cancelled',
  OPEN: 'badge-open',
  CONFIRMED: 'badge-active',
  REMEDIATED: 'badge-completed',
  FALSE_POSITIVE: 'badge-cancelled',
  ACCEPTED_RISK: 'badge-info',
  CREATED: 'badge-draft',
  QUEUED: 'badge-info',
  VALIDATING: 'badge-info',
  RUNNING: 'badge-active',
  RECOVERED: 'badge-recovered',
  EXHAUSTED: 'badge-exhausted',
  FAILED: 'badge-failed',
}

function normalizeStatus(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const cls = STATUS_CLASSES[status.toUpperCase()] ?? ''
  return <span className={`badge ${cls}`}>{normalizeStatus(status)}</span>
}
