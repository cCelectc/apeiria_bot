import type {
  AIModelProfileItem,
  AIModelRouteBindingItem,
  AIModelRouteItem,
  AIModelRouteMemberItem,
} from '@/api/ai'
import { computed, reactive, ref, type Ref } from 'vue'
import {
  deleteAIModelRoute,
  deleteAIModelRouteBinding,
  deleteAIModelRouteMember,
  getAIModelRouteBindings,
  getAIModelRouteMembers,
  getAIModelRoutes,
  upsertAIModelRoute,
  upsertAIModelRouteBinding,
  upsertAIModelRouteMember,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import {
  buildRouteSnapshot,
  type RouteFormState,
} from '@/composables/aiModels/formState'
import type { NoticeLevel, RouteTouchedField } from './helpers'
import { newRouteMember, taskClassValues } from './helpers'

export function useAIModelRoutes(
  t: (key: string, params?: Record<string, unknown>) => string,
  notifyFn: (message: string, level: NoticeLevel) => void,
  isChatCapability: Ref<boolean>,
  filteredModelProfiles: Ref<AIModelProfileItem[]>,
) {
  const modelRoutes = ref<AIModelRouteItem[]>([])
  const modelRouteMembers = ref<AIModelRouteMemberItem[]>([])
  const modelRouteBindings = ref<AIModelRouteBindingItem[]>([])

  const savingRoute = ref(false)
  const deletingRouteId = ref('')
  const routeBaseline = ref('')
  const routeSubmitAttempted = ref(false)

  const routeTouched = reactive<Record<RouteTouchedField, boolean>>({
    name: false,
  })

  const routeForm = reactive<RouteFormState>({
    algorithm: 'ordered',
    enabled: true,
    fallback_on_failure: true,
    members: [],
    mode: 'primary_fallback',
    name: '',
    route_id: '',
    task_class: 'reply_default',
  })

  function taskClassTitle(value: string) {
    const titleMap: Record<string, string> = {
      memory_extraction: 'ai.modelTaskClassMemoryExtraction',
      planner_light: 'ai.modelTaskClassPlannerLight',
      reasoning_heavy: 'ai.modelTaskClassReasoningHeavy',
      reply_default: 'ai.modelTaskClassReplyDefault',
      reply_roleplay: 'ai.modelTaskClassReplyRoleplay',
      tool_orchestration: 'ai.modelTaskClassToolOrchestration',
    }
    return t(titleMap[value] ?? value)
  }

  const taskClassOptions = computed(() => taskClassValues.map(value => ({
    title: taskClassTitle(value),
    value,
  })))

  const filteredModelRoutes = computed(() => modelRoutes.value.filter(
    item => taskClassValues.includes(item.task_class),
  ))
  const modelRouteCount = computed(() => filteredModelRoutes.value.length)
  const isCreatingRoute = computed(() => routeForm.route_id.length === 0)

  const routeErrors = computed(() => ({
    members: routeForm.members.filter(item => !item.deleted).length === 0
      ? t('ai.modelRouteMemberRequired')
      : '',
    name: routeForm.name.trim().length === 0
      ? t('ai.modelRouteNameRequired')
      : '',
  }))
  const displayedRouteErrors = computed(() => ({
    members: routeSubmitAttempted.value ? routeErrors.value.members : '',
    name: routeTouched.name || routeSubmitAttempted.value
      ? routeErrors.value.name
      : '',
  }))
  const routeValid = computed(() => (
    !routeErrors.value.name && !routeErrors.value.members
  ))
  const routeDirty = computed(() => (
    buildRouteSnapshot(routeForm) !== routeBaseline.value
  ))
  const canSaveRoute = computed(() => (
    isChatCapability.value
    && routeValid.value
    && routeDirty.value
    && !savingRoute.value
  ))

  const selectedRouteBindingCount = computed(() => (
    modelRouteBindings.value.filter(item => item.route_id === routeForm.route_id).length
  ))
  const selectedRouteMembers = computed(() => routeForm.members
    .filter(item => !item.deleted)
    .sort((left, right) => left.position - right.position))
  const routeProfileOptions = computed(() => filteredModelProfiles.value.map(item => ({
    title: item.name,
    value: item.profile_id,
  })))

  function resetRouteValidation() {
    routeSubmitAttempted.value = false
    routeTouched.name = false
  }

  function syncRouteBaseline() {
    routeBaseline.value = buildRouteSnapshot(routeForm)
  }

  function touchRouteField(field: RouteTouchedField) {
    routeTouched[field] = true
  }

  function selectModelRoute(item: AIModelRouteItem) {
    const members = modelRouteMembers.value
      .filter(member => member.route_id === item.route_id)
      .sort((left, right) => (
        left.position - right.position
        || left.route_member_id.localeCompare(right.route_member_id)
      ))
      .map(member => ({
        enabled: member.enabled,
        position: member.position,
        profile_id: member.profile_id,
        route_member_id: member.route_member_id,
        weight: member.weight,
      }))
    Object.assign(routeForm, {
      algorithm: item.algorithm,
      enabled: item.enabled,
      fallback_on_failure: item.fallback_on_failure,
      members,
      mode: item.mode,
      name: item.name,
      route_id: item.route_id,
      task_class: item.task_class,
    })
    syncRouteBaseline()
    resetRouteValidation()
  }

  function startCreateModelRoute() {
    Object.assign(routeForm, {
      algorithm: 'ordered',
      enabled: true,
      fallback_on_failure: true,
      members: filteredModelProfiles.value[0]
        ? [newRouteMember(filteredModelProfiles.value[0].profile_id, 0)]
        : [],
      mode: 'primary_fallback',
      name: '',
      route_id: '',
      task_class: 'reply_default',
    })
    syncRouteBaseline()
    resetRouteValidation()
  }

  function syncActiveRouteSelection() {
    if (!isChatCapability.value) {
      startCreateModelRoute()
      return
    }
    const current = filteredModelRoutes.value.find(
      item => item.route_id === routeForm.route_id,
    )
    if (current) {
      selectModelRoute(current)
      return
    }
    if (filteredModelRoutes.value.length > 0) {
      selectModelRoute(filteredModelRoutes.value[0])
      return
    }
    startCreateModelRoute()
  }

  function setRouteMode(mode: string) {
    routeForm.mode = mode
    routeForm.algorithm = mode === 'load_balance' ? 'weighted_random' : 'ordered'
  }

  function addRouteMember(profileId?: string) {
    const selectedProfileId = profileId
      ?? routeProfileOptions.value.find(option => (
        !selectedRouteMembers.value.some(member => member.profile_id === option.value)
      ))?.value
      ?? routeProfileOptions.value[0]?.value
      ?? ''
    if (!selectedProfileId) {
      return
    }
    routeForm.members.push(
      newRouteMember(selectedProfileId, selectedRouteMembers.value.length),
    )
    normalizeRouteMemberPositions()
  }

  function removeRouteMember(index: number) {
    const member = selectedRouteMembers.value[index]
    if (!member) {
      return
    }
    if (member.route_member_id) {
      member.deleted = true
    } else {
      const memberIndex = routeForm.members.indexOf(member)
      if (memberIndex >= 0) {
        routeForm.members.splice(memberIndex, 1)
      }
    }
    normalizeRouteMemberPositions()
  }

  function moveRouteMember(index: number, direction: -1 | 1) {
    const visible = selectedRouteMembers.value
    const current = visible[index]
    const target = visible[index + direction]
    if (!current || !target) {
      return
    }
    const currentPosition = current.position
    current.position = target.position
    target.position = currentPosition
    normalizeRouteMemberPositions()
  }

  function normalizeRouteMemberPositions() {
    selectedRouteMembers.value
      .sort((left, right) => left.position - right.position)
      .forEach((member, index) => {
        member.position = index
      })
  }

  async function saveModelRoute() {
    routeSubmitAttempted.value = true
    if (!routeValid.value) {
      notifyFn(
        routeErrors.value.name
        || routeErrors.value.members
        || t('ai.modelRouteSaveFailed'),
        'error',
      )
      return
    }
    if (!routeDirty.value) {
      return
    }
    savingRoute.value = true
    try {
      normalizeRouteMemberPositions()
      const response = await upsertAIModelRoute({
        algorithm: routeForm.mode === 'load_balance' ? 'weighted_random' : 'ordered',
        enabled: routeForm.enabled,
        fallback_on_failure: routeForm.fallback_on_failure,
        mode: routeForm.mode,
        name: routeForm.name.trim(),
        route_id: routeForm.route_id || null,
        task_class: routeForm.task_class,
      })
      if (!response.data) {
        throw new Error(t('ai.modelRouteSaveFailed'))
      }
      const routeId = response.data.route_id
      for (const member of routeForm.members) {
        if (member.deleted) {
          if (member.route_member_id) {
            await deleteAIModelRouteMember(member.route_member_id)
          }
          continue
        }
        await upsertAIModelRouteMember({
          enabled: member.enabled,
          position: member.position,
          profile_id: member.profile_id,
          route_id: routeId,
          route_member_id: member.route_member_id || null,
          weight: Math.max(1, Number(member.weight) || 1),
        })
      }
      await upsertAIModelRouteBinding({
        route_id: routeId,
        scope_id: '__global__',
        scope_type: 'global',
        task_class: routeForm.task_class,
      })
      await refreshRouteData()
      const selectedRoute = modelRoutes.value.find(item => item.route_id === routeId)
      if (selectedRoute) {
        selectModelRoute(selectedRoute)
      }
      notifyFn(t('ai.modelRouteSaved'), 'success')
    } catch (error) {
      notifyFn(getErrorMessage(error, t('ai.modelRouteSaveFailed')), 'error')
    } finally {
      savingRoute.value = false
    }
  }

  async function removeModelRoute() {
    if (!routeForm.route_id) {
      return
    }
    deletingRouteId.value = routeForm.route_id
    try {
      for (const binding of modelRouteBindings.value.filter(
        item => item.route_id === routeForm.route_id,
      )) {
        await deleteAIModelRouteBinding({
          scope_id: binding.scope_id,
          scope_type: binding.scope_type,
          task_class: binding.task_class,
        })
      }
      await deleteAIModelRoute(routeForm.route_id)
      await refreshRouteData()
      syncActiveRouteSelection()
      notifyFn(t('ai.modelRouteDeleted'), 'success')
    } catch (error) {
      notifyFn(getErrorMessage(error, t('ai.modelRouteDeleteFailed')), 'error')
    } finally {
      deletingRouteId.value = ''
    }
  }

  async function refreshRouteData() {
    const [routesResponse, membersResponse, bindingsResponse] = await Promise.all([
      getAIModelRoutes(),
      getAIModelRouteMembers(),
      getAIModelRouteBindings(),
    ])
    modelRoutes.value = routesResponse.data
    modelRouteMembers.value = membersResponse.data
    modelRouteBindings.value = bindingsResponse.data
  }

  return {
    canSaveRoute,
    deletingRouteId,
    displayedRouteErrors,
    filteredModelRoutes,
    isCreatingRoute,
    modelRouteBindings,
    modelRouteCount,
    modelRouteMembers,
    modelRoutes,
    routeForm,
    routeProfileOptions,
    savingRoute,
    selectedRouteBindingCount,
    selectedRouteMembers,
    taskClassOptions,

    addRouteMember,
    moveRouteMember,
    removeModelRoute,
    removeRouteMember,
    saveModelRoute,
    selectModelRoute,
    setRouteMode,
    startCreateModelRoute,
    syncActiveRouteSelection,
    touchRouteField,
    refreshRouteData,
  }
}
