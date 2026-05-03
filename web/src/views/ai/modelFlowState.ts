import type { AISetupRouteIntent } from './routeState'
import type {
  AISetupDependency,
  AISetupNextActionKind,
  AISetupStepKey,
} from '@/composables/aiModels/setupWorkflow'

export type AIModelFlowHighlight
  = | 'connection'
    | 'defaultModel'
    | 'fetch'
    | 'import'
    | 'model'
    | 'profile'
    | 'provider'
    | 'test'

export type AIModelFlowAutoOpen
  = | 'connection'
    | 'modelEditor'
    | 'profileEditor'
    | 'providerEditor'

export interface AIModelFlowFocus {
  step: AISetupStepKey
  highlight: AIModelFlowHighlight
  autoOpen: AIModelFlowAutoOpen | null
  remoteOperation: boolean
}

interface AIModelFlowFocusInput {
  intent: AISetupRouteIntent | ''
  workflowDependency: AISetupDependency
  workflowNextAction: AISetupNextActionKind
  workflowTargetStep: AISetupStepKey
}

const intentFocusMap: Record<AISetupRouteIntent, AIModelFlowFocus> = {
  connection: {
    autoOpen: 'connection',
    highlight: 'connection',
    remoteOperation: false,
    step: 'connection',
  },
  createModel: {
    autoOpen: 'modelEditor',
    highlight: 'model',
    remoteOperation: false,
    step: 'model',
  },
  createProfile: {
    autoOpen: 'profileEditor',
    highlight: 'profile',
    remoteOperation: false,
    step: 'profile',
  },
  createProvider: {
    autoOpen: 'providerEditor',
    highlight: 'provider',
    remoteOperation: false,
    step: 'provider',
  },
  defaultModel: {
    autoOpen: 'modelEditor',
    highlight: 'defaultModel',
    remoteOperation: false,
    step: 'defaultModel',
  },
  fetchModels: {
    autoOpen: null,
    highlight: 'fetch',
    remoteOperation: true,
    step: 'discovery',
  },
  importModel: {
    autoOpen: null,
    highlight: 'import',
    remoteOperation: true,
    step: 'model',
  },
  profile: {
    autoOpen: 'profileEditor',
    highlight: 'profile',
    remoteOperation: false,
    step: 'profile',
  },
  validation: {
    autoOpen: null,
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

export function resolveAIModelFlowIntent (
  intent: AISetupRouteIntent,
): AIModelFlowFocus {
  return intentFocusMap[intent]
}

export function resolveAIModelFlowFocus ({
  intent,
  workflowDependency,
  workflowNextAction,
  workflowTargetStep,
}: AIModelFlowFocusInput): AIModelFlowFocus {
  if (intent) {
    return resolveAIModelFlowIntent(intent)
  }
  const actionFocus = actionFocusMap[workflowNextAction]
  if (actionFocus.step === workflowTargetStep) {
    return actionFocus
  }
  return dependencyFocusMap[workflowDependency]
}
