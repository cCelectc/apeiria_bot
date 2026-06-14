import client from '@/api/client'
import type {
  AIModelRouteBindingItem,
  AIModelRouteItem,
  AIModelRouteMemberItem,
} from './types'

export function getAIModelRoutes() {
  return client.get<AIModelRouteItem[]>('/ai/model-routes')
}

export function upsertAIModelRoute(payload: {
  route_id?: string | null
  name: string
  task_class: string
  mode: string
  algorithm: string
  fallback_on_failure: boolean
  enabled: boolean
}) {
  return client.put<AIModelRouteItem | null>('/ai/model-routes', payload)
}

export function deleteAIModelRoute(routeId: string) {
  return client.delete<boolean>('/ai/model-routes', {
    params: { route_id: routeId },
  })
}

export function getAIModelRouteMembers(routeId?: string) {
  return client.get<AIModelRouteMemberItem[]>('/ai/model-route-members', {
    params: routeId ? { route_id: routeId } : undefined,
  })
}

export function upsertAIModelRouteMember(payload: {
  route_member_id?: string | null
  route_id: string
  profile_id: string
  position: number
  weight: number
  enabled: boolean
}) {
  return client.put<AIModelRouteMemberItem | null>('/ai/model-route-members', payload)
}

export function deleteAIModelRouteMember(routeMemberId: string) {
  return client.delete<boolean>('/ai/model-route-members', {
    params: { route_member_id: routeMemberId },
  })
}

export function getAIModelRouteBindings() {
  return client.get<AIModelRouteBindingItem[]>('/ai/model-route-bindings')
}

export function upsertAIModelRouteBinding(payload: {
  scope_type: string
  scope_id: string
  task_class: string
  route_id: string
}) {
  return client.put<AIModelRouteBindingItem>('/ai/model-route-bindings', payload)
}

export function deleteAIModelRouteBinding(payload: {
  scope_type: string
  scope_id: string
  task_class: string
}) {
  return client.delete<boolean>('/ai/model-route-bindings', { params: payload })
}
