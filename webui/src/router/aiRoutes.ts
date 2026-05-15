export type AIManagementPage =
  | 'overview'
  | 'sessions'
  | 'models'
  | 'personas'
  | 'knowledge'
  | 'memories'
  | 'relationships'
  | 'profiles'
  | 'futureTasks'
  | 'skills'
  | 'debug'

export type AIManagementRouteName =
  | 'ai-overview'
  | 'ai-sessions'
  | 'ai-models'
  | 'ai-personas'
  | 'ai-knowledge'
  | 'ai-memories'
  | 'ai-relationships'
  | 'ai-profiles'
  | 'ai-future-tasks'
  | 'ai-skills'
  | 'ai-debug'

export interface AIManagementPageDescriptor {
  icon: string
  page: AIManagementPage
  path: string
  routeName: AIManagementRouteName
  titleKey: string
}

export const aiManagementPageDescriptors: AIManagementPageDescriptor[] = [
  {
    icon: 'LayoutDashboard',
    page: 'overview',
    path: '/ai/overview',
    routeName: 'ai-overview',
    titleKey: 'ai.overviewTitle',
  },
  {
    icon: 'MessagesSquare',
    page: 'sessions',
    path: '/ai/sessions',
    routeName: 'ai-sessions',
    titleKey: 'ai.sessionsTab',
  },
  {
    icon: 'ServerCog',
    page: 'models',
    path: '/ai/models',
    routeName: 'ai-models',
    titleKey: 'ai.modelsTitle',
  },
  {
    icon: 'MessagesSquare',
    page: 'personas',
    path: '/ai/personas',
    routeName: 'ai-personas',
    titleKey: 'ai.personasTab',
  },
  {
    icon: 'BookOpenCheck',
    page: 'knowledge',
    path: '/ai/knowledge',
    routeName: 'ai-knowledge',
    titleKey: 'ai.knowledgeTab',
  },
  {
    icon: 'Brain',
    page: 'memories',
    path: '/ai/memories',
    routeName: 'ai-memories',
    titleKey: 'ai.memoryTab',
  },
  {
    icon: 'Network',
    page: 'relationships',
    path: '/ai/relationships',
    routeName: 'ai-relationships',
    titleKey: 'ai.relationshipTab',
  },
  {
    icon: 'ContactRound',
    page: 'profiles',
    path: '/ai/profiles',
    routeName: 'ai-profiles',
    titleKey: 'ai.profileTab',
  },
  {
    icon: 'CalendarClock',
    page: 'futureTasks',
    path: '/ai/future-tasks',
    routeName: 'ai-future-tasks',
    titleKey: 'ai.futureTaskTab',
  },
  {
    icon: 'Wrench',
    page: 'skills',
    path: '/ai/skills',
    routeName: 'ai-skills',
    titleKey: 'ai.skillsTab',
  },
  {
    icon: 'Bug',
    page: 'debug',
    path: '/ai/debug',
    routeName: 'ai-debug',
    titleKey: 'ai.debugTab',
  },
]
