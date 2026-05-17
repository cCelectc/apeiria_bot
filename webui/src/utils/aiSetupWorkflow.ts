export type AISetupStatus = 'degraded' | 'usable'

export type AISetupDependency =
  | 'connection'
  | 'defaultModel'
  | 'model'
  | 'profile'
  | 'provider'
  | 'ready'

export type AISetupNextActionKind =
  | 'completeConnection'
  | 'createModel'
  | 'createProfile'
  | 'createProvider'
  | 'fetchModels'
  | 'importModel'
  | 'saveModel'
  | 'saveProfile'
  | 'saveProvider'
  | 'setDefaultModel'
  | 'testModel'

export type AISetupStepKey =
  | 'connection'
  | 'defaultModel'
  | 'discovery'
  | 'model'
  | 'profile'
  | 'provider'
  | 'validation'

export type AISetupStepState = 'blocked' | 'complete' | 'current' | 'pending'

export type AIWorkflowResultStage =
  | 'discovery'
  | 'model'
  | 'profile'
  | 'provider'
  | 'validation'

export type AIWorkflowResultStatus = 'error' | 'success' | 'warning'

export interface AIWorkflowOperationResult {
  status: AIWorkflowResultStatus
  message: string
  detail?: string
}

export interface AISetupSourceSummary {
  source_id: string
  name: string
  enabled: boolean
  preset_type: string
  api_base: string | null
  api_keys?: string[]
}

export interface AISetupModelSummary {
  model_id: string
  source_id: string
  model_identifier: string
  display_name: string
  enabled: boolean
  is_default: boolean
}

export interface AISetupProfileSummary {
  profile_id: string
  name: string
  model_id: string
  task_class: string
  priority: number
  enabled: boolean
  fallback_profile_id: string | null
}

export interface AISetupWorkflowInput {
  capabilityType: string
  sourceCount: number
  selectedSource: AISetupSourceSummary | null
  sourceModels: AISetupModelSummary[]
  modelProfiles: AISetupProfileSummary[]
  fetchedSourceModelCount: number
  canFetchSourceModels: boolean
  canSaveSource: boolean
  canSaveModel: boolean
  canSaveProfile: boolean
}

export interface AISetupStep {
  key: AISetupStepKey
  state: AISetupStepState
  action: AISetupNextActionKind | null
  reason: string
}

export interface AISetupNextAction {
  kind: AISetupNextActionKind
  targetStep: AISetupStepKey
}

export interface AISetupWorkflow {
  status: AISetupStatus
  dependency: AISetupDependency
  nextAction: AISetupNextAction
  progress: {
    complete: number
    total: number
  }
  selectedModel: AISetupModelSummary | null
  defaultModel: AISetupModelSummary | null
  defaultReplyProfile: AISetupProfileSummary | null
  connectionIssues: Array<'apiBase' | 'apiKey' | 'disabled' | 'preset'>
  steps: AISetupStep[]
}

function hasText(value: string | null | undefined) {
  return typeof value === 'string' && value.trim().length > 0
}

function hasApiKey(source: AISetupSourceSummary) {
  return (source.api_keys ?? []).some(value => hasText(value))
}

function resolveConnectionIssues(source: AISetupSourceSummary | null) {
  const issues: AISetupWorkflow['connectionIssues'] = []
  if (!source) {
    return issues
  }
  if (!source.enabled) {
    issues.push('disabled')
  }
  if (!hasText(source.preset_type)) {
    issues.push('preset')
  }
  if (!hasText(source.api_base)) {
    issues.push('apiBase')
  }
  if (!hasApiKey(source)) {
    issues.push('apiKey')
  }
  return issues
}

function createStep(
  key: AISetupStepKey,
  state: AISetupStepState,
  action: AISetupNextActionKind | null = null,
  reason = '',
): AISetupStep {
  return { action, key, reason, state }
}

function resolveMissingModelAction(input: AISetupWorkflowInput): AISetupNextAction {
  if (input.fetchedSourceModelCount > 0) {
    return {
      kind: 'importModel',
      targetStep: 'model',
    }
  }
  if (input.canFetchSourceModels) {
    return {
      kind: 'fetchModels',
      targetStep: 'discovery',
    }
  }
  if (input.canSaveModel) {
    return {
      kind: 'saveModel',
      targetStep: 'discovery',
    }
  }
  return {
    kind: 'createModel',
    targetStep: 'discovery',
  }
}

export function deriveAISetupWorkflow(input: AISetupWorkflowInput): AISetupWorkflow {
  const selectedSource = input.selectedSource
  const hasProvider = input.sourceCount > 0 && !!selectedSource?.source_id
  const connectionIssues = resolveConnectionIssues(selectedSource)
  const connectionReady = hasProvider && connectionIssues.length === 0
  const enabledModels = input.sourceModels.filter(item => item.enabled)
  const defaultModel = enabledModels.find(item => item.is_default) ?? null
  const selectedModel = defaultModel ?? enabledModels[0] ?? input.sourceModels[0] ?? null
  const needsProfile = input.capabilityType === 'chat_completion'
  const modelIds = new Set(input.sourceModels.map(item => item.model_id))
  const defaultReplyProfile = input.modelProfiles.find(item => (
    item.enabled
    && item.task_class === 'reply_default'
    && modelIds.has(item.model_id)
  )) ?? null

  let steps: AISetupStep[]
  let dependency: AISetupDependency = 'ready'
  let nextAction: AISetupNextAction = {
    kind: 'testModel',
    targetStep: 'validation',
  }

  if (!hasProvider) {
    dependency = 'provider'
    nextAction = {
      kind: input.canSaveSource ? 'saveProvider' : 'createProvider',
      targetStep: 'provider',
    }
    steps = [
      createStep('provider', 'current', nextAction.kind),
      createStep('connection', 'pending'),
      createStep('discovery', 'pending'),
      createStep('model', 'pending'),
      createStep('defaultModel', 'pending'),
      createStep('profile', needsProfile ? 'pending' : 'complete'),
      createStep('validation', 'pending'),
    ]
  } else if (!connectionReady) {
    dependency = 'connection'
    nextAction = {
      kind: input.canSaveSource ? 'saveProvider' : 'completeConnection',
      targetStep: 'connection',
    }
    steps = [
      createStep('provider', 'complete'),
      createStep('connection', 'current', nextAction.kind, connectionIssues[0] ?? ''),
      createStep('discovery', 'blocked', null, 'connection'),
      createStep('model', 'pending'),
      createStep('defaultModel', 'pending'),
      createStep('profile', needsProfile ? 'pending' : 'complete'),
      createStep('validation', 'pending'),
    ]
  } else if (enabledModels.length === 0) {
    dependency = 'model'
    nextAction = resolveMissingModelAction(input)
    const hasFetchedModels = input.fetchedSourceModelCount > 0
    steps = [
      createStep('provider', 'complete'),
      createStep('connection', 'complete'),
      createStep('discovery', hasFetchedModels ? 'complete' : 'current', nextAction.kind),
      createStep('model', hasFetchedModels ? 'current' : 'pending', nextAction.kind),
      createStep('defaultModel', 'pending'),
      createStep('profile', needsProfile ? 'pending' : 'complete'),
      createStep('validation', 'pending'),
    ]
  } else if (!defaultModel) {
    dependency = 'defaultModel'
    nextAction = {
      kind: input.canSaveModel ? 'saveModel' : 'setDefaultModel',
      targetStep: 'defaultModel',
    }
    steps = [
      createStep('provider', 'complete'),
      createStep('connection', 'complete'),
      createStep('discovery', 'complete'),
      createStep('model', 'complete'),
      createStep('defaultModel', 'current', nextAction.kind),
      createStep('profile', needsProfile ? 'pending' : 'complete'),
      createStep('validation', 'pending'),
    ]
  } else if (needsProfile && !defaultReplyProfile) {
    dependency = 'profile'
    nextAction = {
      kind: input.canSaveProfile ? 'saveProfile' : 'createProfile',
      targetStep: 'profile',
    }
    steps = [
      createStep('provider', 'complete'),
      createStep('connection', 'complete'),
      createStep('discovery', 'complete'),
      createStep('model', 'complete'),
      createStep('defaultModel', 'complete'),
      createStep('profile', 'current', nextAction.kind),
      createStep('validation', 'pending'),
    ]
  } else {
    steps = [
      createStep('provider', 'complete'),
      createStep('connection', 'complete'),
      createStep('discovery', 'complete'),
      createStep('model', 'complete'),
      createStep('defaultModel', 'complete'),
      createStep('profile', 'complete'),
      createStep('validation', 'complete', 'testModel'),
    ]
  }

  const complete = steps.filter(step => step.state === 'complete').length
  const status: AISetupStatus = complete === steps.length ? 'usable' : 'degraded'

  return {
    connectionIssues,
    defaultModel,
    defaultReplyProfile,
    dependency,
    nextAction,
    progress: {
      complete,
      total: steps.length,
    },
    selectedModel,
    status,
    steps,
  }
}

export function resolveAISetupActionRoute(
  action: AISetupNextActionKind,
  capability = 'chat',
) {
  const intentMap: Record<AISetupNextActionKind, string> = {
    completeConnection: 'connection',
    createModel: 'createModel',
    createProfile: 'createProfile',
    createProvider: 'createProvider',
    fetchModels: 'fetchModels',
    importModel: 'importModel',
    saveModel: 'defaultModel',
    saveProfile: 'profile',
    saveProvider: 'connection',
    setDefaultModel: 'defaultModel',
    testModel: 'validation',
  }
  return {
    name: 'ai',
    query: {
      area: 'models',
      capability,
      intent: intentMap[action],
    },
  }
}
