import type { AdapterConfigItem } from '@/api/adapters'

export type CoreTranslate = (
  key: string,
  params?: Record<string, unknown>,
) => string

export interface AdapterDraftRow {
  id: string
  value: string
}

export interface AdapterDraftDiagnostics {
  addedModules: string[]
  blankRowCount: number
  duplicateModules: string[]
  normalizedModules: string[]
  removedModules: string[]
  unchangedModules: string[]
}

export function normalizeAdapterModules(values: string[]) {
  return Array.from(
    new Set(
      values
        .map(value => value.trim())
        .filter(Boolean),
    ),
  ).sort((left, right) => left.localeCompare(right))
}

export function buildAdapterDraftDiagnostics(
  draftValues: string[],
  savedValues: string[],
): AdapterDraftDiagnostics {
  const trimmedValues = draftValues.map(value => value.trim())
  const normalizedModules = normalizeAdapterModules(draftValues)
  const savedModules = normalizeAdapterModules(savedValues)
  const savedSet = new Set(savedModules)
  const normalizedSet = new Set(normalizedModules)
  const seenModules = new Set<string>()
  const duplicateModules = new Set<string>()

  for (const value of trimmedValues) {
    if (!value) {
      continue
    }
    if (seenModules.has(value)) {
      duplicateModules.add(value)
    }
    seenModules.add(value)
  }

  return {
    addedModules: normalizedModules.filter(value => !savedSet.has(value)),
    blankRowCount: trimmedValues.filter(value => !value).length,
    duplicateModules: [...duplicateModules].sort((left, right) =>
      left.localeCompare(right),
    ),
    normalizedModules,
    removedModules: savedModules.filter(value => !normalizedSet.has(value)),
    unchangedModules: normalizedModules.filter(value => savedSet.has(value)),
  }
}

export function adapterStatusSummary(
  item: AdapterConfigItem | undefined,
  t: CoreTranslate,
) {
  if (!item) {
    return t('core.adapterUnsaved')
  }
  if (item.is_loaded) {
    return t('plugins.moduleLoaded')
  }
  if (item.is_importable) {
    return t('plugins.moduleRegisteredOnly')
  }
  return t('plugins.moduleMissing')
}
