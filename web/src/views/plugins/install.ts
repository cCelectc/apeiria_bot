import type { PluginTranslate } from '@/views/plugins/display'

export type ManualInstallSourceType = 'pypi' | 'git' | 'local'

export function manualInstallSourceOptions (t: PluginTranslate) {
  return [
    { value: 'pypi', label: t('plugins.manualInstallSourcePypi') },
    { value: 'git', label: t('plugins.manualInstallSourceGit') },
    { value: 'local', label: t('plugins.manualInstallSourceLocal') },
  ]
}

export function manualInstallRequirementLabel (
  sourceType: ManualInstallSourceType,
  t: PluginTranslate,
) {
  if (sourceType === 'git') {
    return t('plugins.manualInstallGitLabel')
  }
  if (sourceType === 'local') {
    return t('plugins.manualInstallLocalLabel')
  }
  return t('plugins.manualInstallPackageLabel')
}

export function manualInstallRequirementHint (
  sourceType: ManualInstallSourceType,
  t: PluginTranslate,
) {
  if (sourceType === 'git') {
    return t('plugins.manualInstallGitHint')
  }
  if (sourceType === 'local') {
    return t('plugins.manualInstallLocalHint')
  }
  return t('plugins.manualInstallPackageHint')
}

export function canSubmitManualInstall (requirement: string) {
  return requirement.trim().length > 0
}
