export type StoreSortMode = 'default' | 'name' | 'updated'

export interface StoreRouteState {
  category: string
  installedOnly: boolean
  page: number
  search: string
  sort: StoreSortMode
  source: string
}

const supportedSortModes = new Set<StoreSortMode>(['default', 'name', 'updated'])

export function normalizeStoreRouteState(query: Record<string, unknown>): StoreRouteState {
  return {
    category: firstString(query.category).trim(),
    installedOnly: normalizeInstalledOnly(query.installed),
    page: normalizePage(query.page),
    search: firstString(query.search).trim(),
    sort: normalizeSort(query.sort),
    source: firstString(query.source).trim(),
  }
}

export function buildStoreRouteQuery(state: StoreRouteState): Record<string, string> {
  const query: Record<string, string> = {}
  if (state.search.trim()) {
    query.search = state.search.trim()
  }
  if (state.source.trim()) {
    query.source = state.source.trim()
  }
  if (state.category.trim()) {
    query.category = state.category.trim()
  }
  if (state.sort !== 'default') {
    query.sort = state.sort
  }
  if (state.page > 1) {
    query.page = String(state.page)
  }
  query.installed = state.installedOnly ? 'hidden' : 'all'
  return query
}

export function storeRouteStateEquals(
  left: StoreRouteState,
  right: StoreRouteState,
): boolean {
  return left.category === right.category
    && left.installedOnly === right.installedOnly
    && left.page === right.page
    && left.search === right.search
    && left.sort === right.sort
    && left.source === right.source
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

function normalizeSort(value: unknown): StoreSortMode {
  const rawValue = firstString(value)
  return supportedSortModes.has(rawValue as StoreSortMode)
    ? rawValue as StoreSortMode
    : 'default'
}

function normalizePage(value: unknown): number {
  const rawValue = firstString(value)
  const page = Number.parseInt(rawValue, 10)
  return Number.isFinite(page) && page > 1 ? page : 1
}

function normalizeInstalledOnly(value: unknown): boolean {
  const rawValue = firstString(value)
  return rawValue !== 'all'
}
