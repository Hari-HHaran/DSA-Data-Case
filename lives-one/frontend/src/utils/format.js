// Pure formatting helpers (unit-tested in format.test.js).

export const STATUS_META = {
  DRAFT: { label: 'Draft', tone: 'neutral', icon: 'pencil' },
  SUBMITTED: { label: 'Submitted', tone: 'info', icon: 'send' },
  VALIDATION_COMPLETED: { label: 'Details checked', tone: 'info', icon: 'check' },
  PENDING_APPROVAL: { label: 'Waiting for approval', tone: 'warning', icon: 'clock' },
  NEEDS_CHANGES: { label: 'Sent back for changes', tone: 'warning', icon: 'alert' },
  REJECTED: { label: 'Not approved', tone: 'error', icon: 'x' },
  APPROVED: { label: 'Approved', tone: 'success', icon: 'check' },
  MDM_VERIFICATION: { label: 'Final check', tone: 'info', icon: 'shield' },
  SAP_PENDING: { label: 'Being set up in SAP', tone: 'info', icon: 'clock' },
  SAP_COMPLETED: { label: 'Ready to use (in SAP)', tone: 'success', icon: 'check' },
  SAP_FAILED: { label: 'SAP set-up failed', tone: 'error', icon: 'alert' },
  CANCELLED: { label: 'Cancelled', tone: 'neutral', icon: 'x' },
  // approval tasks
  PENDING: { label: 'Waiting for decision', tone: 'warning', icon: 'clock' },
  WAITING: { label: 'Waiting for an earlier step', tone: 'neutral', icon: 'pause' },
  CHANGES_REQUESTED: { label: 'Sent back for changes', tone: 'warning', icon: 'alert' },
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
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min`
  if (h < 48) { const n = Math.round(h); return `${n} hour${n === 1 ? '' : 's'}` }
  const d = Math.round(h / 24)
  return `${d} days`
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
  REQUESTOR: 'Requester', BU_HEAD: 'Business Unit Head', FINANCE: 'Finance', QRA: 'Quality & Regulatory', BUSINESS_SUPPORT: 'Business Support',
  MDM_ANALYST: 'Master Data team', ADMIN: 'Administrator', SALES: 'Regional Sales', EXECUTIVE: 'Executive (view only)',
}

// Everyday names for history / activity events. Anything not listed falls back to humanize().
export const EVENT_LABELS = {
  STATUS_SUBMITTED: 'Request submitted', ROUTED: 'Sent to approvers', TASK_APPROVED: 'Approved', TASK_REJECTED: 'Not approved',
  TASK_CHANGES_REQUESTED: 'Sent back for changes', RETURNED_FOR_CHANGES: 'Sent back for changes', REQUEST_REJECTED: 'Request not approved',
  SAP_CREATION_COMPLETED: 'Created in SAP', SAP_CREATION_FAILED: 'SAP set-up failed', SAP_MANUAL_RESOLUTION: 'Marked as created in SAP by hand',
  SLA_REMINDER: 'Reminder sent', ESCALATED: 'Escalated (overdue)', DRAFT_CREATED: 'Draft started', DRAFT_UPDATED: 'Draft saved',
  DUPLICATE_PREVENTED: 'Duplicate avoided', DUPLICATE_CHECK_RUN: 'Checked for duplicates', DUPLICATE_REVIEWED: 'Duplicate check decided',
  SUBMISSION_BLOCKED: 'Submit stopped: details missing', FOLLOWUP_ASSIGNED: 'Follow-up assigned', MAPPING_CONFIRMED: 'Customer names linked',
  MAPPING_REJECTED: 'Customer names kept separate', REQUEST_CANCELLED: 'Request cancelled', MDM_VERIFIED: 'Final check passed',
  MDM_VERIFICATION_READY: 'Ready for final check', ATTACHMENT_ADDED: 'Document added', ATTACHMENT_REMOVED: 'Document removed',
  STAGE_ADVANCED: 'Moved to the next approval step', APPROVAL_ASSIGNED: 'Approval assigned', APPROVAL_COMPLETED: 'All approvals done',
  REQUEST_SUBMITTED: 'Request submitted', FORM_CONFIG_CHANGED: 'Request form changed', WORKFLOW_CONFIG_CHANGED: 'Approval rules changed',
  SETTING_CHANGED: 'Setting changed', USER_LOGIN: 'Signed in',
}
export const eventLabel = (code) => EVENT_LABELS[code] || humanize(code)
