import { describe, expect, it } from 'vitest'
import { evalCondition, fmtPct, fmtNumber, humanize, relTime, statusMeta, monthLabel } from './format.js'

describe('format helpers', () => {
  it('formats percentages with sign', () => {
    expect(fmtPct(0.123, 1, true)).toBe('+12.3%')
    expect(fmtPct(-0.05)).toBe('-5%')
    expect(fmtPct(null)).toBe('—')
  })
  it('formats numbers and handles missing values', () => {
    expect(fmtNumber(1234.5)).toBe('1,235')
    expect(fmtNumber(undefined)).toBe('—')
  })
  it('humanizes codes and maps statuses', () => {
    expect(humanize('SAP_FAILED')).toBe('Sap failed')
    expect(statusMeta('SAP_COMPLETED').tone).toBe('success')
    expect(statusMeta('UNKNOWN_X').label).toBe('Unknown x')
  })
  it('renders relative time', () => {
    const now = Date.parse('2026-10-22T10:00:00Z')
    expect(relTime('2026-10-22T08:00:00Z', now)).toBe('2 hours ago')
    expect(relTime('2026-10-24T10:00:00Z', now)).toBe('in 2 days')
  })
  it('labels months', () => {
    expect(monthLabel('2026-09')).toMatch(/Sep/)
  })
})

describe('condition language (mirrors backend)', () => {
  const reg = { all: [{ field: 'regulatory_class', op: 'in', value: ['Class B', 'Class C', 'Class D'] }] }
  it('evaluates in / all', () => {
    expect(evalCondition(reg, { regulatory_class: 'Class B' })).toBe(true)
    expect(evalCondition(reg, { regulatory_class: 'Class A' })).toBe(false)
  })
  it('treats empty condition as always true and supports any/neq', () => {
    expect(evalCondition(null, {})).toBe(true)
    const c = { any: [{ field: 'payment_terms', op: 'neq', value: 'Cash in advance' }, { field: 'x', op: 'exists' }] }
    expect(evalCondition(c, { payment_terms: 'Net 30' })).toBe(true)
    expect(evalCondition(c, { payment_terms: 'Cash in advance' })).toBe(false)
  })
})
