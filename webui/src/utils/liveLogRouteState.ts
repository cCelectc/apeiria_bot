export interface LiveLogRouteState {
  advanced: boolean
  levels: string[]
  search: string
  showAccessLogs: boolean
  showRawRecords: boolean
  sources: string[]
}

export function normalizeLiveLogRouteState(
  query: Record<string, unknown>,
): LiveLogRouteState {
  return {
    advanced: normalizeFlag(query.advanced),
    levels: normalizeStringList(query.level),
    search: firstString(query.search).trim(),
    showAccessLogs: normalizeFlag(query.access),
    showRawRecords: normalizeFlag(query.raw),
    sources: normalizeStringList(query.source),
  }
}

export function buildLiveLogRouteQuery(
  state: LiveLogRouteState,
): Record<string, string> {
  const query: Record<string, string> = {}
  if (state.search.trim()) {
    query.search = state.search.trim()
  }
  if (state.levels.length > 0) {
    query.level = normalizeList(state.levels).join(',')
  }
  if (state.sources.length > 0) {
    query.source = normalizeList(state.sources).join(',')
  }
  if (state.showAccessLogs) {
    query.access = '1'
  }
  if (state.showRawRecords) {
    query.raw = '1'
  }
  if (state.advanced) {
    query.advanced = '1'
  }
  return query
}

export function liveLogRouteStateEquals(
  left: LiveLogRouteState,
  right: LiveLogRouteState,
): boolean {
  return left.advanced === right.advanced
    && left.search === right.search
    && left.showAccessLogs === right.showAccessLogs
    && left.showRawRecords === right.showRawRecords
    && stringListsEqual(left.levels, right.levels)
    && stringListsEqual(left.sources, right.sources)
}

function normalizeStringList(value: unknown): string[] {
  const values = Array.isArray(value) ? value : [value]
  return normalizeList(
    values.flatMap(item => {
      if (typeof item !== 'string') {
        return []
      }
      return item.split(',')
    }),
  )
}

function normalizeList(values: string[]): string[] {
  return Array.from(new Set(
    values
      .map(item => item.trim())
      .filter(Boolean),
  )).sort()
}

function normalizeFlag(value: unknown): boolean {
  const rawValue = firstString(value).trim().toLowerCase()
  return rawValue === '1' || rawValue === 'true' || rawValue === 'yes'
}

function firstString(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return value.find(item => typeof item === 'string') ?? ''
  }
  return ''
}

function stringListsEqual(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false
  }
  return left.every((item, index) => item === right[index])
}
