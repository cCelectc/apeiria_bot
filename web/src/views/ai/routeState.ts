export type AIManagementPage
  = | 'overview'
    | 'models'
    | 'personas'
    | 'memories'
    | 'relationships'
    | 'profiles'
    | 'skills'
    | 'debug'

export type AIManagementRouteName
  = | 'ai-overview'
    | 'ai-models'
    | 'ai-personas'
    | 'ai-memories'
    | 'ai-relationships'
    | 'ai-profiles'
    | 'ai-skills'
    | 'ai-debug'

export type AISourceCapabilityRouteValue
  = | 'chat'
    | 'embedding'
    | 'stt'
    | 'tts'
    | 'rerank'

export type AIDebugRouteValue = 'conversations' | 'futureTasks' | 'tools'

export type AISetupActionKind
  = | 'completeConnection'
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

export type AISetupRouteIntent
  = | 'connection'
    | 'createModel'
    | 'createProfile'
    | 'createProvider'
    | 'defaultModel'
    | 'fetchModels'
    | 'importModel'
    | 'profile'
    | 'validation'

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

export interface AIRouteTarget {
  name: AIManagementRouteName
  query: Record<string, string>
}

export interface AIManagementPageDescriptor {
  icon: string
  page: AIManagementPage
  path: string
  routeName: AIManagementRouteName
  titleKey: string
}

export const aiManagementPages: AIManagementPage[] = [
  'overview',
  'models',
  'personas',
  'memories',
  'relationships',
  'profiles',
  'skills',
  'debug',
]

export const aiPageRouteNames: Record<AIManagementPage, AIManagementRouteName> = {
  debug: 'ai-debug',
  memories: 'ai-memories',
  models: 'ai-models',
  overview: 'ai-overview',
  personas: 'ai-personas',
  profiles: 'ai-profiles',
  relationships: 'ai-relationships',
  skills: 'ai-skills',
}

export const aiRouteNamePages: Record<AIManagementRouteName, AIManagementPage> = {
  'ai-debug': 'debug',
  'ai-memories': 'memories',
  'ai-models': 'models',
  'ai-overview': 'overview',
  'ai-personas': 'personas',
  'ai-profiles': 'profiles',
  'ai-relationships': 'relationships',
  'ai-skills': 'skills',
}

export const aiManagementPageDescriptors: AIManagementPageDescriptor[] = [
  {
    icon: 'mdi-view-dashboard-outline',
    page: 'overview',
    path: '/ai/overview',
    routeName: 'ai-overview',
    titleKey: 'ai.overviewTitle',
  },
  {
    icon: 'mdi-server-network',
    page: 'models',
    path: '/ai/models',
    routeName: 'ai-models',
    titleKey: 'ai.modelsTitle',
  },
  {
    icon: 'mdi-account-voice',
    page: 'personas',
    path: '/ai/personas',
    routeName: 'ai-personas',
    titleKey: 'ai.personasTab',
  },
  {
    icon: 'mdi-brain',
    page: 'memories',
    path: '/ai/memories',
    routeName: 'ai-memories',
    titleKey: 'ai.memoryTab',
  },
  {
    icon: 'mdi-account-heart-outline',
    page: 'relationships',
    path: '/ai/relationships',
    routeName: 'ai-relationships',
    titleKey: 'ai.relationshipTab',
  },
  {
    icon: 'mdi-account-box-outline',
    page: 'profiles',
    path: '/ai/profiles',
    routeName: 'ai-profiles',
    titleKey: 'ai.personProfileTab',
  },
  {
    icon: 'mdi-tools',
    page: 'skills',
    path: '/ai/skills',
    routeName: 'ai-skills',
    titleKey: 'ai.skillsTab',
  },
  {
    icon: 'mdi-bug-check-outline',
    page: 'debug',
    path: '/ai/debug',
    routeName: 'ai-debug',
    titleKey: 'ai.debugTab',
  },
]

const supportedCapabilities = new Set<AISourceCapabilityRouteValue>([
  'chat',
  'embedding',
  'stt',
  'tts',
  'rerank',
])

const supportedDebugTabs = new Set<AIDebugRouteValue>([
  'conversations',
  'futureTasks',
  'tools',
])

function firstString (value: unknown) {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return value.find(item => typeof item === 'string') ?? ''
  }
  return ''
}

export function normalizeAISetupRouteIntent (
  value: unknown,
): AISetupRouteIntent | '' {
  const rawValue = firstString(value)
  return supportedSetupRouteIntents.has(rawValue as AISetupRouteIntent)
    ? rawValue as AISetupRouteIntent
    : ''
}

export function normalizeAICapabilityRouteValue (
  value: unknown,
): AISourceCapabilityRouteValue {
  const rawValue = firstString(value)
  return supportedCapabilities.has(rawValue as AISourceCapabilityRouteValue)
    ? rawValue as AISourceCapabilityRouteValue
    : 'chat'
}

export function normalizeAIDebugRouteValue (value: unknown): AIDebugRouteValue {
  const rawValue = firstString(value)
  return supportedDebugTabs.has(rawValue as AIDebugRouteValue)
    ? rawValue as AIDebugRouteValue
    : 'conversations'
}

export function resolveAISetupActionIntent (
  action: AISetupActionKind,
): AISetupRouteIntent {
  const intentMap: Record<AISetupActionKind, AISetupRouteIntent> = {
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
  return intentMap[action]
}

export function resolveAISetupActionRoute (
  action: AISetupActionKind,
  capability: unknown,
): AIRouteTarget {
  return {
    name: 'ai-models',
    query: {
      capability: normalizeAICapabilityRouteValue(capability),
      intent: resolveAISetupActionIntent(action),
    },
  }
}
