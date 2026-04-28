import type { AdapterConfigItem } from '@/api/adapters'

export type CoreTranslate = (
  key: string,
  params?: Record<string, unknown>,
) => string

export interface AdapterDraftRow {
  id: string
  value: string
}

export function normalizeAdapterModules (values: string[]) {
  return Array.from(
    new Set(
      values
        .map(value => value.trim())
        .filter(Boolean),
    ),
  ).toSorted((left, right) => left.localeCompare(right))
}

export function buildAdapterDraftRows (modules: string[]) {
  return modules.map((value, index) => ({
    id: `adapter-module-${index}`,
    value,
  }))
}

export function adapterStatusSummary (
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
