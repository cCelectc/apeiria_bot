import type { RouteMemberFormState } from '@/composables/aiModels/formState'

export type NoticeLevel = 'error' | 'success' | 'warning'
export type SourceTouchedField = 'name' | 'preset_type'
export type ModelTouchedField = 'display_name' | 'model_identifier'
export type ProfileTouchedField = 'model_id' | 'name'
export type RouteTouchedField = 'name'
export type AIProviderDetailMode = 'creating' | 'empty' | 'selected'

export const taskClassValues = [
  'reply_default',
  'reply_roleplay',
  'tool_orchestration',
  'memory_extraction',
  'planner_light',
  'reasoning_heavy',
]

export function newRouteMember(
  profileId: string,
  position: number,
): RouteMemberFormState {
  return {
    enabled: true,
    position,
    profile_id: profileId,
    route_member_id: '',
    weight: 1,
  }
}
