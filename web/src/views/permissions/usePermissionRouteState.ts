import type { Perspective } from '@/views/permissions/options'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { ref } from 'vue'

export function usePermissionRouteState (route: RouteLocationNormalizedLoaded) {
  const perspective = ref<Perspective>('plugins')

  function applyRouteState (): void {
    const tabQuery = route.query.tab
    if (tabQuery === 'plugins' || tabQuery === 'users' || tabQuery === 'rules') {
      perspective.value = tabQuery
    }
  }

  return {
    applyRouteState,
    perspective,
  }
}
