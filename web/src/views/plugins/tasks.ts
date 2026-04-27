import type { PluginStoreTask } from '@/api/plugins'
import type { PluginTranslate } from '@/views/plugins/display'

export function summarizeTaskError (message: string | null | undefined) {
  const normalized = message?.trim()
  if (!normalized) {
    return ''
  }
  return normalized.split('\n')[0]?.trim() || normalized
}

export function manualInstallTaskStatusLabel (
  task: PluginStoreTask | null,
  t: PluginTranslate,
) {
  const status = task?.status || ''
  if (status === 'pending') {
    return t('plugins.manualInstallPending')
  }
  if (status === 'running') {
    return t('plugins.manualInstallRunning')
  }
  if (status === 'succeeded') {
    return t('plugins.manualInstallSucceeded')
  }
  if (status === 'failed') {
    return summarizeTaskError(task?.error) || t('plugins.manualInstallFailed')
  }
  return ''
}

export function packageUpdateTaskStatusLabel (
  task: PluginStoreTask | null,
  t: PluginTranslate,
) {
  const status = task?.status || ''
  if (status === 'pending') {
    return t('plugins.packageUpdatePending')
  }
  if (status === 'running') {
    return t('plugins.packageUpdateRunning')
  }
  if (status === 'succeeded') {
    return t('plugins.packageUpdateSucceeded')
  }
  if (status === 'failed') {
    return summarizeTaskError(task?.error) || t('plugins.packageUpdateFailed')
  }
  return ''
}
