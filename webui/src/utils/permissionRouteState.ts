import type {
  LocationQueryRaw,
  RouteLocationNormalizedLoaded,
  Router,
} from 'vue-router'
import { ref, watch } from 'vue'
import {
  type PermissionPerspective,
  normalizePermissionPerspective,
} from '@/utils/permissions'

export function usePermissionRouteState(
  route: RouteLocationNormalizedLoaded,
  router: Router,
) {
  const perspective = ref<PermissionPerspective>('plugins')
  let applyingRouteState = false

  function readRoutePerspective() {
    return normalizePermissionPerspective(route.query.section || route.query.tab)
  }

  function applyRouteState() {
    const nextPerspective = readRoutePerspective()
    if (perspective.value === nextPerspective) {
      return
    }
    applyingRouteState = true
    perspective.value = nextPerspective
    applyingRouteState = false
  }

  function syncRouteState() {
    if (route.query.section === perspective.value && route.query.tab === undefined) {
      return
    }
    const query: LocationQueryRaw = {
      ...route.query,
      section: perspective.value,
    }
    delete query.tab
    void router.replace({ query })
  }

  watch(() => perspective.value, () => {
    if (!applyingRouteState) {
      syncRouteState()
    }
  }, { flush: 'sync' })

  return {
    applyRouteState,
    perspective,
  }
}
