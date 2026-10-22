// Shared ECharts styling. Colour follows the entity (family/country), never its rank or filter position.
import { monthLabel, fmtNumber } from './format.js'

export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
export const FAMILY_COLORS = { A: SERIES[0], B: SERIES[1], C: SERIES[2] }
export const COUNTRY_ORDER = ['SG', 'MY', 'ID', 'TH', 'VN']
export const countryColor = (code) => SERIES[Math.max(0, COUNTRY_ORDER.indexOf(code)) % SERIES.length]
export const SEQ_BLUE = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
export const INK = { text: '#172033', muted: '#64748b', grid: '#eef1f6', axis: '#cfd7e4' }

export function baseGrid(extra = {}) {
  return { left: 8, right: 16, top: 52, bottom: 8, containLabel: true, ...extra }
}

export function axisCategory(data, extra = {}) {
  return { type: 'category', data, axisLine: { lineStyle: { color: INK.axis } }, axisTick: { show: false },
    axisLabel: { color: INK.muted, fontSize: 11 }, ...extra }
}

export function axisValue(name, extra = {}) {
  return { type: 'value', name, nameLocation: 'end', nameGap: 8, nameTextStyle: { color: INK.muted, fontSize: 11, align: 'right', padding: [0, 0, 0, 0] }, splitLine: { lineStyle: { color: INK.grid } },
    axisLabel: { color: INK.muted, fontSize: 11, formatter: (v) => fmtNumber(v) }, ...extra }
}

export function tooltip(extra = {}) {
  return { trigger: 'axis', backgroundColor: '#101c35', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 },
    axisPointer: { type: 'line', lineStyle: { color: '#94a3b8', type: 'dashed' } }, valueFormatter: (v) => (v == null ? '—' : fmtNumber(v)), ...extra }
}

export function legend(extra = {}) {
  return { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: INK.text, fontSize: 12 }, ...extra }
}

export const months = (arr) => arr.map(monthLabel)

export function lineSeries(name, data, color, extra = {}) {
  return { name, type: 'line', data, smooth: false, symbol: 'circle', symbolSize: 7, showSymbol: true, lineStyle: { width: 2, color },
    itemStyle: { color, borderColor: '#fff', borderWidth: 2 }, emphasis: { focus: 'series' }, ...extra }
}

export function barSeries(name, data, color, extra = {}) {
  return { name, type: 'bar', data, barMaxWidth: 26, itemStyle: { color, borderRadius: [4, 4, 0, 0], borderColor: '#fff', borderWidth: 1 },
    emphasis: { focus: 'series' }, ...extra }
}

// Diverging: red (decline) ↔ neutral gray ↔ blue (growth).
export const DIVERGING = ['#b83232', '#e88a89', '#f0efec', '#86b6ef', '#256abf']
