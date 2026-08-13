import type { EChartsOption } from 'echarts'

export type ChartType = 'bar' | 'line' | 'pie' | 'table' | 'kpi'

export interface ChartSpec {
  id: string
  chart_type: ChartType
  title: string
  subtitle?: string
  x?: string
  y?: string
  data: Array<Record<string, unknown>>
  provenance: string[]
  warnings: string[]
  chartable: boolean
}

export type MessageSegment =
  | { type: 'markdown'; content: string }
  | { type: 'chart'; chart: ChartSpec }

const CHART_TYPES = new Set<ChartType>(['bar', 'line', 'pie', 'table', 'kpi'])
const DOCUMENT_KEYS = new Set(['type', 'version', 'charts'])
const SPEC_KEYS = new Set([
  'id', 'chart_type', 'title', 'subtitle', 'x', 'y', 'data',
  'provenance', 'warnings', 'chartable',
])
const FENCED_BLOCK = /```(?:json)?\s*\r?\n([\s\S]*?)\r?\n```/gi

export function parseMessageSegments(content: string): MessageSegment[] {
  const segments: MessageSegment[] = []
  let cursor = 0

  for (const match of content.matchAll(FENCED_BLOCK)) {
    const index = match.index ?? 0
    appendMarkdownWithInlineDocuments(segments, content.slice(cursor, index))
    const charts = parseChartDocument((match[1] ?? '').trim())
    if (charts) {
      segments.push(...charts.map((chart): MessageSegment => ({ type: 'chart', chart })))
    } else {
      appendMarkdown(segments, match[0])
    }
    cursor = index + match[0].length
  }

  appendMarkdownWithInlineDocuments(segments, content.slice(cursor))
  return segments
}

export function chartSpecToEChartsOption(spec: ChartSpec): EChartsOption | null {
  if (!spec.chartable || spec.chart_type === 'table' || spec.chart_type === 'kpi') {
    return null
  }

  const base: EChartsOption = {
    color: ['#1677ff', '#13a8a8', '#fa8c16', '#722ed1', '#eb2f96', '#52c41a'],
    tooltip: { trigger: spec.chart_type === 'pie' ? 'item' : 'axis' },
    grid: { left: 48, right: 24, top: 24, bottom: 40, containLabel: true },
  }
  if (spec.chart_type === 'bar' || spec.chart_type === 'line') {
    return {
      ...base,
      xAxis: {
        type: 'category',
        data: spec.data.map((row) => toCategoryValue(row[spec.x ?? ''])),
      },
      yAxis: { type: 'value' },
      series: [{
        name: spec.y,
        type: spec.chart_type,
        data: spec.data.map((row) => toNumericValue(row[spec.y ?? ''])),
        smooth: spec.chart_type === 'line',
      }],
    }
  }
  return {
    ...base,
    legend: { bottom: 0 },
    series: [{
      name: spec.title,
      type: 'pie',
      radius: ['35%', '68%'],
      data: spec.data.map((row) => ({
        name: toCategoryValue(row[spec.x ?? '']),
        value: toNumericValue(row[spec.y ?? '']) ?? 0,
      })),
    }],
  }
}

function appendMarkdownWithInlineDocuments(segments: MessageSegment[], content: string): void {
  const lines = content.split(/(\r?\n)/)
  for (const part of lines) {
    const charts = part.includes('\n') ? null : parseChartDocument(part.trim())
    if (charts) {
      segments.push(...charts.map((chart): MessageSegment => ({ type: 'chart', chart })))
    } else {
      appendMarkdown(segments, part)
    }
  }
}

function appendMarkdown(segments: MessageSegment[], content: string): void {
  if (!content) return
  const previous = segments.at(-1)
  if (previous?.type === 'markdown') previous.content += content
  else segments.push({ type: 'markdown', content })
}

function parseChartDocument(candidate: string): ChartSpec[] | null {
  if (!candidate.startsWith('{')) return null
  let value: unknown
  try {
    value = JSON.parse(candidate)
  } catch {
    return null
  }
  if (!isRecord(value) || value.type !== 'chart') return null
  if (!hasOnlyKeys(value, DOCUMENT_KEYS) || value.version !== '1.0') return null
  if (!Array.isArray(value.charts) || value.charts.length < 1 || value.charts.length > 12) {
    return null
  }
  const charts = value.charts.map(parseChartSpec)
  return charts.every((chart): chart is ChartSpec => chart !== null) ? charts : null
}

function parseChartSpec(value: unknown): ChartSpec | null {
  if (!isRecord(value) || !hasOnlyKeys(value, SPEC_KEYS)) return null
  if (!isBoundedString(value.id, 120) || !isBoundedString(value.title, 200)) return null
  if (typeof value.chart_type !== 'string' || !CHART_TYPES.has(value.chart_type as ChartType)) return null
  if (value.subtitle !== undefined && !isBoundedString(value.subtitle, 300, true)) return null
  if (value.x !== undefined && !isBoundedString(value.x, 120)) return null
  if (value.y !== undefined && !isBoundedString(value.y, 120)) return null
  if (!Array.isArray(value.data) || value.data.length > 500) return null
  if (!value.data.every((row) => isRecord(row) && Object.keys(row).length <= 30)) return null
  if (value.provenance !== undefined && !isStringList(value.provenance, 30)) return null
  if (value.warnings !== undefined && !isStringList(value.warnings, 30)) return null
  if (value.chartable !== undefined && typeof value.chartable !== 'boolean') return null

  const chartType = value.chart_type as ChartType
  const x = typeof value.x === 'string' ? value.x : undefined
  const y = typeof value.y === 'string' ? value.y : undefined
  if (['bar', 'line', 'pie'].includes(chartType)) {
    if (!x || !y || !value.data.every((row) => x in row && y in row)) return null
  }
  return {
    id: value.id as string,
    chart_type: chartType,
    title: value.title as string,
    ...(typeof value.subtitle === 'string' ? { subtitle: value.subtitle } : {}),
    ...(x ? { x } : {}),
    ...(y ? { y } : {}),
    data: value.data as Array<Record<string, unknown>>,
    provenance: (value.provenance as string[] | undefined) ?? [],
    warnings: (value.warnings as string[] | undefined) ?? [],
    chartable: (value.chartable as boolean | undefined) ?? true,
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasOnlyKeys(value: Record<string, unknown>, allowed: Set<string>): boolean {
  return Object.keys(value).every((key) => allowed.has(key))
}

function isBoundedString(value: unknown, max: number, allowEmpty = false): value is string {
  return typeof value === 'string' && value.length <= max && (allowEmpty || value.length > 0)
}

function isStringList(value: unknown, max: number): value is string[] {
  return Array.isArray(value) && value.length <= max && value.every((item) => typeof item === 'string')
}

function toCategoryValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function toNumericValue(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value !== 'string' || !value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}
