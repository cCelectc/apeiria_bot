import type {
  AICapabilityItem,
  AICapabilityPreviewItem,
  AISkillItem,
  AIToolExecutionItem,
  AIToolIntentPreviewItem,
  AIToolItem,
  AIToolPolicyBindingItem,
  AIToolPolicyPreviewItem,
} from './types'

import client from '../client'

export function getAITools () {
  return client.get<AIToolItem[]>('/ai/tools')
}

export function getAISkills () {
  return client.get<AISkillItem[]>('/ai/skills')
}

export function getAICapabilities () {
  return client.get<AICapabilityItem[]>('/ai/tools/capabilities')
}

export function getAIToolExecutions (params: {
  scene_id: string
}) {
  return client.get<AIToolExecutionItem[]>('/ai/tools/executions', { params })
}

export function getAIToolPolicyBindings () {
  return client.get<AIToolPolicyBindingItem[]>('/ai/tools/policy-bindings')
}

export function createAIToolPolicyBinding (payload: {
  scope_type: string
  scope_id: string
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolPolicyBindingItem>(
    '/ai/tools/policy-bindings',
    payload,
  )
}

export function updateAIToolPolicyBinding (payload: {
  binding_id: string
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.patch<AIToolPolicyBindingItem | null>(
    '/ai/tools/policy-bindings',
    payload,
  )
}

export function deleteAIToolPolicyBinding (bindingId: string) {
  return client.delete<{ deleted: boolean }>('/ai/tools/policy-bindings', {
    params: { binding_id: bindingId },
  })
}

export function previewAIToolPolicy (payload: {
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolPolicyPreviewItem>(
    '/ai/tools/policy-preview',
    payload,
  )
}

export function previewAIToolIntents (payload: {
  message_text: string
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolIntentPreviewItem[]>(
    '/ai/tools/intent-preview',
    payload,
  )
}

export function previewAISkillPolicyDebug (payload: {
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AIToolPolicyPreviewItem>(
    '/ai/debug/skills/policy-preview',
    payload,
  )
}

export function previewAICapability (payload: {
  capability_name: string
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AICapabilityPreviewItem>(
    '/ai/tools/capability-preview',
    payload,
  )
}

export function previewAISkillCapabilityDebug (payload: {
  capability_name: string
  scope_type: string
  is_tome: boolean
  allow_read_only_tools: boolean
  capability_mode: string
}) {
  return client.post<AICapabilityPreviewItem>(
    '/ai/debug/skills/capability-preview',
    payload,
  )
}
