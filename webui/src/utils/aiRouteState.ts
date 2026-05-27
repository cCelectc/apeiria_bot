import type {
  AISetupDependency,
  AISetupNextActionKind,
  AISetupStepKey,
} from '@/utils/aiSetupWorkflow'

export type AISourceCapabilityRouteValue =
  | 'chat'
  | 'embedding'
  | 'stt'
  | 'tts'
  | 'rerank'

export type AISetupRouteIntent =
  | 'connection'
  | 'createModel'
  | 'createProfile'
  | 'createProvider'
  | 'defaultModel'
  | 'fetchModels'
  | 'importModel'
  | 'profile'
  | 'validation'

export type AIModelFlowHighlight =
  | 'connection'
  | 'defaultModel'
  | 'fetch'
  | 'import'
  | 'model'
  | 'profile'
  | 'provider'
  | 'test'

export type AIDebugRouteValue = 'conversations' | 'futureTasks'
export type AIWorkbenchRouteArea =
  | 'debug'
  | 'futureTasks'
  | 'knowledge'
  | 'memories'
  | 'models'
  | 'personas'
  | 'profiles'
  | 'relationships'
  | 'runtimeSettings'
  | 'sessions'
  | 'skills'
  | 'tools'

export interface AIWorkbenchRouteState {
  area: AIWorkbenchRouteArea
  localMode: {
    capability: AISourceCapabilityRouteValue
    debug: AIDebugRouteValue
  }
  selectedIds: {
    model: string
    profile: string
    session: string
    source: string
    trace: string
  }
}

export interface AIModelFlowFocus {
  step: AISetupStepKey
  highlight: AIModelFlowHighlight
  remoteOperation: boolean
}

const supportedCapabilities = new Set<AISourceCapabilityRouteValue>([
  'chat',
  'embedding',
  'stt',
  'tts',
  'rerank',
])

const supportedSetupRouteIntents = new Set<AISetupRouteIntent>([
  'connection',
  'createModel',
  'createProfile',
  'createProvider',
  'defaultModel',
  'fetchModels',
  'importModel',
  'profile',
  'validation',
])

const supportedDebugRouteValues = new Set<AIDebugRouteValue>([
  'conversations',
  'futureTasks',
])

const supportedWorkbenchAreas = new Set<AIWorkbenchRouteArea>([
  'debug',
  'futureTasks',
  'knowledge',
  'memories',
  'models',
  'personas',
  'profiles',
  'relationships',
  'runtimeSettings',
  'sessions',
  'skills',
  'tools',
])

const supportedWorkbenchQueryKeys = new Set([
  'area',
  'capability',
  'debug',
  'model',
  'profile',
  'session',
  'source',
  'trace',
])

const intentFocusMap: Record<AISetupRouteIntent, AIModelFlowFocus> = {
  connection: {
    highlight: 'connection',
    remoteOperation: false,
    step: 'connection',
  },
  createModel: {
    highlight: 'model',
    remoteOperation: false,
    step: 'model',
  },
  createProfile: {
    highlight: 'profile',
    remoteOperation: false,
    step: 'profile',
  },
  createProvider: {
    highlight: 'provider',
    remoteOperation: false,
    step: 'provider',
  },
  defaultModel: {
    highlight: 'defaultModel',
    remoteOperation: false,
    step: 'defaultModel',
  },
  fetchModels: {
    highlight: 'fetch',
    remoteOperation: true,
    step: 'discovery',
  },
  importModel: {
    highlight: 'import',
    remoteOperation: true,
    step: 'model',
  },
  profile: {
    highlight: 'profile',
    remoteOperation: false,
    step: 'profile',
  },
  validation: {
    highlight: 'test',
    remoteOperation: true,
    step: 'validation',
  },
}

const actionFocusMap: Record<AISetupNextActionKind, AIModelFlowFocus> = {
  completeConnection: intentFocusMap.connection,
  createModel: intentFocusMap.createModel,
  createProfile: intentFocusMap.createProfile,
  createProvider: intentFocusMap.createProvider,
  fetchModels: intentFocusMap.fetchModels,
  importModel: intentFocusMap.importModel,
  saveModel: intentFocusMap.defaultModel,
  saveProfile: intentFocusMap.profile,
  saveProvider: intentFocusMap.connection,
  setDefaultModel: intentFocusMap.defaultModel,
  testModel: intentFocusMap.validation,
}

const dependencyFocusMap: Record<AISetupDependency, AIModelFlowFocus> = {
  connection: intentFocusMap.connection,
  defaultModel: intentFocusMap.defaultModel,
  model: intentFocusMap.createModel,
  profile: intentFocusMap.profile,
  provider: intentFocusMap.createProvider,
  ready: intentFocusMap.validation,
}

function firstString(value: unknown) {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return value.find(item => typeof item === 'string') ?? ''
  }
  return ''
}

export function normalizeAICapabilityRouteValue(
  value: unknown,
): AISourceCapabilityRouteValue {
  const rawValue = firstString(value)
  return supportedCapabilities.has(rawValue as AISourceCapabilityRouteValue)
    ? rawValue as AISourceCapabilityRouteValue
    : 'chat'
}

export function normalizeAISetupRouteIntent(
  value: unknown,
): AISetupRouteIntent | '' {
  const rawValue = firstString(value)
  return supportedSetupRouteIntents.has(rawValue as AISetupRouteIntent)
    ? rawValue as AISetupRouteIntent
    : ''
}

export function normalizeAIDebugRouteValue(value: unknown): AIDebugRouteValue {
  const rawValue = firstString(value)
  return supportedDebugRouteValues.has(rawValue as AIDebugRouteValue)
    ? rawValue as AIDebugRouteValue
    : 'conversations'
}

export function normalizeAIWorkbenchArea(value: unknown): AIWorkbenchRouteArea {
  const rawValue = firstString(value)
  if (supportedWorkbenchAreas.has(rawValue as AIWorkbenchRouteArea)) {
    return rawValue as AIWorkbenchRouteArea
  }
  return 'models'
}

export function normalizeAIWorkbenchRouteState(
  query: Record<string, unknown>,
): AIWorkbenchRouteState {
  return {
    area: normalizeAIWorkbenchArea(query.area),
    localMode: {
      capability: normalizeAICapabilityRouteValue(query.capability),
      debug: normalizeAIDebugRouteValue(query.debug),
    },
    selectedIds: {
      model: firstString(query.model),
      profile: firstString(query.profile),
      session: firstString(query.session),
      source: firstString(query.source),
      trace: firstString(query.trace),
    },
  }
}

export function buildAIWorkbenchAreaQuery(
  area: AIWorkbenchRouteArea,
  currentQuery: Record<string, unknown>,
): Record<string, string> {
  const nextQuery: Record<string, string> = {}
  for (const [key, value] of Object.entries(currentQuery)) {
    if (!supportedWorkbenchQueryKeys.has(key) || key === 'area') {
      continue
    }
    const stringValue = firstString(value)
    if (stringValue) {
      nextQuery[key] = stringValue
    }
  }
  nextQuery.area = area
  return nextQuery
}

export function resolveAIModelFlowFocus(input: {
  intent: AISetupRouteIntent | ''
  workflowDependency: AISetupDependency
  workflowNextAction: AISetupNextActionKind
  workflowTargetStep: AISetupStepKey
}): AIModelFlowFocus {
  if (input.intent) {
    return intentFocusMap[input.intent]
  }
  const actionFocus = actionFocusMap[input.workflowNextAction]
  if (actionFocus.step === input.workflowTargetStep) {
    return actionFocus
  }
  return dependencyFocusMap[input.workflowDependency]
}
