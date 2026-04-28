import type { Perspective } from '@/views/permissions/options'
import type {
  LocationQueryRaw,
  RouteLocationNormalizedLoaded,
  Router,
} from 'vue-router'
import { ref, watch } from 'vue'

const perspectiveTabs = new Set<Perspective>(['plugins', 'users', 'rules'])

export function usePermissionRouteState (
  route: RouteLocationNormalizedLoaded,
  router: Router,
) {
  const perspective = ref<Perspective>('plugins')
  let applyingRouteState = false

  function resolvePerspective (): Perspective {
    const tabQuery = route.query.section || route.query.tab
    return typeof tabQuery === 'string' && perspectiveTabs.has(tabQuery as Perspective)
      ? tabQuery as Perspective
      : 'plugins'
  }

  function applyRouteState (): void {
    const nextPerspective = resolvePerspective()
    if (perspective.value === nextPerspective) {
      return
    }
    applyingRouteState = true
    perspective.value = nextPerspective
    applyingRouteState = false
  }

  function syncRouteState (): void {
    if (route.query.section === perspective.value && route.query.tab === undefined) {
      return
    }
    const query: LocationQueryRaw = {
      ...route.query,
      section: perspective.value,
    }
    delete query.tab
    void router.replace({
      query,
    })
  }

  watch(() => perspective.value, () => {
    if (applyingRouteState) {
      return
    }
    syncRouteState()
  }, { flush: 'sync' })

  return {
    applyRouteState,
    perspective,
  }
}
