import type {
  LocationQueryRaw,
  RouteLocationNormalizedLoaded,
  Router,
} from 'vue-router'
import { ref, watch } from 'vue'

export type CoreSectionTab = 'core' | 'adapters' | 'drivers'

const coreSectionTabs = new Set<CoreSectionTab>(['core', 'adapters', 'drivers'])

export function useCoreRouteState (
  route: RouteLocationNormalizedLoaded,
  router: Router,
) {
  const sectionTab = ref<CoreSectionTab>('core')
  let applyingRouteState = false

  function resolveSectionTab (): CoreSectionTab {
    const sectionQuery = route.query.section
    return typeof sectionQuery === 'string' && coreSectionTabs.has(sectionQuery as CoreSectionTab)
      ? sectionQuery as CoreSectionTab
      : 'core'
  }

  function applyRouteState (): void {
    const nextTab = resolveSectionTab()
    if (sectionTab.value === nextTab) {
      return
    }
    applyingRouteState = true
    sectionTab.value = nextTab
    applyingRouteState = false
  }

  function syncRouteState (): void {
    if (route.query.section === sectionTab.value) {
      return
    }
    const query: LocationQueryRaw = {
      ...route.query,
      section: sectionTab.value,
    }
    void router.replace({ query })
  }

  applyRouteState()

  watch(() => sectionTab.value, () => {
    if (applyingRouteState) {
      return
    }
    syncRouteState()
  }, { flush: 'sync' })

  watch(() => route.query.section, () => {
    applyRouteState()
  })

  return {
    applyRouteState,
    sectionTab,
  }
}
