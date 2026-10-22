// Pure formatting helpers (unit-tested in format.test.js).

export const STATUS_META = {
  DRAFT: { label: 'Draft', tone: 'neutral', icon: 'pencil' },
  SUBMITTED: { label: 'Submitted', tone: 'info', icon: 'send' },
  VALIDATION_COMPLETED: { label: 'Validated', tone: 'info', icon: 'check' },
  PENDING_APPROVAL: { label: 'Pending approval', tone: 'warning', icon: 'clock' },
  NEEDS_CHANGES: { label: 'Needs changes', tone: 'warning', icon: 'alert' },
  REJECTED: { label: 'Rejected', tone: 'error', icon: 'x' },
  APPROVED: { label: 'Approved', tone: 'success', icon: 'check' },
  MDM_VERIFICATION: { label: 'MDM verification', tone: 'info', icon: 'shield' },
  SAP_PENDING: { label: 'SAP creation pending', tone: 'info', icon: 'clock' },
  SAP_COMPLETED: { label: 'Live in SAP B1', tone: 'success', icon: 'check' },
  SAP_FAILED: { label: 'SAP creation failed', tone: 'error', icon: 'alert' },
  CANCELLED: { label: 'Cancelled', tone: 'neutral', icon: 'x' },
  // approval tasks
  PENDING: { label: 'Pending', tone: 'warning', icon: 'clock' },
  WAITING: { label: 'Waiting for earlier stage', tone: 'neutral', icon: 'pause' },
  CHANGES_REQUESTED: { label: 'Changes requested', tone: 'warning', icon: 'alert' },
  // opportunities
  NEW: { label: 'New', tone: 'info', icon: 'sparkle' },
  UNDER_REVIEW: { label: 'Under review', tone: 'info', icon: 'eye' },
  ASSIGNED: { label: 'Assigned', tone: 'info', icon: 'user' },
  IN_PROGRESS: { label: 'In progress', tone: 'warning', icon: 'clock' },
  COMPLETED: { label: 'Completed', tone: 'success', icon: 'check' },
  DISMISSED: { label: 'Dismissed', tone: 'neutral', icon: 'x' },
}

export function statusMeta(code) {
  return STATUS_META[code] || { label: humanize(code), tone: 'neutral', icon: 'dot' }
}

export function humanize(code) {
  if (!code) return ''
  return String(code).toLowerCase().replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function fmtNumber(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toLocaleString('en-SG', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function fmtPct(v, digits = 0, signed = false) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const s = (Number(v) * 100).toFixed(digits)
  return `${signed && v > 0 ? '+' : ''}${s}%`
}

export function fmtMoney(v) {
  if (v === null || v === undefined) return '—'
  return 'S$' + Number(v).toLocaleString('en-SG', { maximumFractionDigits: 0 })
}

export function fmtDate(iso, withTime = false) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const opts = { day: '2-digit', month: 'short', year: 'numeric' }
  if (withTime) Object.assign(opts, { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleString('en-SG', opts)
}

export function relTime(iso, now = Date.now()) {
  if (!iso) return '—'
  const diff = (new Date(iso).getTime() - now) / 1000
  const abs = Math.abs(diff)
  const units = [['day', 86400], ['hour', 3600], ['minute', 60]]
  for (const [u, s] of units) {
    if (abs >= s) {
      const n = Math.round(abs / s)
      return diff < 0 ? `${n} ${u}${n > 1 ? 's' : ''} ago` : `in ${n} ${u}${n > 1 ? 's' : ''}`
    }
  }
  return 'just now'
}

export function monthLabel(ym) {
  if (!ym) return ''
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleString('en-SG', { month: 'short', year: '2-digit' })
}

export function hoursLabel(h) {
  if (h === null || h === undefined) return '—'
  if (h < 1) return `${Math.round(h * 60)} min`
  if (h < 48) return `${h.toFixed(h < 10 ? 1 : 0)} h`
  return `${(h / 24).toFixed(1)} days`
}

// Evaluate the backend's condition language client-side (for instant show/hide; the server re-validates).
export function evalCondition(cond, ctx) {
  if (!cond) return true
  const clauses = cond.all || cond.any || []
  const test = (c) => {
    const v = ctx[c.field]
    switch (c.op) {
      case 'exists': return v !== undefined && v !== null && v !== ''
      case 'not_exists': return v === undefined || v === null || v === ''
      case 'eq': return v === c.value
      case 'neq': return v !== c.value
      case 'in': return (c.value || []).includes(v)
      case 'not_in': return !(c.value || []).includes(v)
      case 'gt': return Number(v) > Number(c.value)
      case 'gte': return Number(v) >= Number(c.value)
      case 'lt': return Number(v) < Number(c.value)
      case 'lte': return Number(v) <= Number(c.value)
      default: return true
    }
  }
  return cond.all ? clauses.every(test) : clauses.some(test)
}

export const ROLE_LABELS = {
  REQUESTOR: 'Requestor', BU_HEAD: 'BU Head', FINANCE: 'Finance', QRA: 'Quality / Regulatory', BUSINESS_SUPPORT: 'Business Support',
  MDM_ANALYST: 'MDM Analyst', ADMIN: 'Administrator', SALES: 'Regional Sales', EXECUTIVE: 'Executive Viewer',
}
