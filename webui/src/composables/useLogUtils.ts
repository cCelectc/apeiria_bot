import type { LogItem } from '@/api/logs'

export interface LogEntry extends LogItem {
  id: string
}

export function toLogEntry(item: LogItem): LogEntry {
  return {
    ...item,
    id: `${item.timestamp}_${item.level}_${item.source}_${Math.random().toString(16).slice(2)}`,
  }
}

export function normalizeLogFrame(frame: string): LogEntry {
  try {
    const parsed = JSON.parse(frame) as Partial<LogItem>
    const raw = parsed.raw || frame
    return {
      id: `${parsed.timestamp || Date.now()}_${Math.random().toString(16).slice(2)}`,
      timestamp: parsed.timestamp || new Date().toISOString(),
      level: parsed.level || 'INFO',
      source: parsed.source || 'unknown',
      message: parsed.message || raw,
      raw,
      extra: parsed.extra && typeof parsed.extra === 'object'
        ? parsed.extra
        : {},
    }
  } catch {
    return {
      id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      timestamp: new Date().toISOString(),
      level: 'INFO',
      source: 'raw',
      message: frame,
      raw: frame,
      extra: {},
    }
  }
}

export function logEntryKey(entry: Pick<LogEntry, 'timestamp' | 'level' | 'source' | 'raw'>) {
  return `${entry.timestamp}|${entry.level}|${entry.source}|${entry.raw}`
}

export function logLevelTone(level: string) {
  const normalized = level.toUpperCase()
  if (normalized === 'ERROR' || normalized === 'CRITICAL') {
    return 'error'
  }
  if (normalized === 'WARNING' || normalized === 'WARN') {
    return 'warning'
  }
  if (normalized === 'SUCCESS') {
    return 'success'
  }
  return 'info'
}

export function logMatchesFilters(
  entry: LogEntry,
  options: {
    levels?: string[]
    search?: string
    showAccessLogs?: boolean
    sources?: string[]
  },
) {
  if (!options.showAccessLogs && entry.source === 'uvicorn.access') {
    return false
  }
  if (options.levels?.length && !options.levels.includes(entry.level)) {
    return false
  }
  if (options.sources?.length && !options.sources.includes(entry.source)) {
    return false
  }
  const keyword = options.search?.trim().toLowerCase()
  if (!keyword) {
    return true
  }
  const haystack = [
    entry.timestamp,
    entry.level,
    entry.source,
    entry.message,
    entry.raw,
    JSON.stringify(entry.extra),
  ].join(' ').toLowerCase()
  return haystack.includes(keyword)
}

export function exportJsonl(entries: unknown[], filename: string) {
  const blob = new Blob(
    [entries.map(entry => JSON.stringify(entry)).join('\n')],
    { type: 'application/jsonl;charset=utf-8' },
  )
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export function formatDateTimeLocal(value: Date) {
  const year = value.getFullYear()
  const month = `${value.getMonth() + 1}`.padStart(2, '0')
  const day = `${value.getDate()}`.padStart(2, '0')
  const hours = `${value.getHours()}`.padStart(2, '0')
  const minutes = `${value.getMinutes()}`.padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}
