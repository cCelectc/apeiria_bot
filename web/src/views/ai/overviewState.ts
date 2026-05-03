import type { AIManagementPage } from './routeState'
import type { AISetupStatus } from '@/composables/aiModels/setupWorkflow'

export function resolveAIOverviewDestinationPages (
  status: AISetupStatus,
): AIManagementPage[] {
  return status === 'usable'
    ? ['models', 'debug']
    : ['models']
}
