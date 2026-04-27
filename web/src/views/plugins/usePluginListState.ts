import type { PluginItem } from '@/api/plugins'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { computed, ref, type Ref } from 'vue'
import {
  buildPluginNameMap,
  getNonSystemPlugins,
  getSystemPlugins,
  getVisiblePlugins,
} from '@/views/plugins/filters'

export function usePluginListState (
  plugins: Ref<PluginItem[]>,
  route: RouteLocationNormalizedLoaded,
) {
  const pluginScopeTab = ref<'managed' | 'framework'>('managed')
  const pluginSearch = ref('')

  const pluginNameMap = computed(() =>
    buildPluginNameMap(plugins.value),
  )
  const systemPlugins = computed(() =>
    getSystemPlugins(plugins.value),
  )
  const nonSystemPlugins = computed(() =>
    getNonSystemPlugins(plugins.value),
  )
  const visiblePlugins = computed(() =>
    getVisiblePlugins(plugins.value, {
      disabledOnly: route.query.enabled === 'disabled',
      scope: pluginScopeTab.value,
      search: pluginSearch.value,
    }),
  )

  function applyRouteFilters () {
    const searchQuery = route.query.search
    pluginSearch.value = typeof searchQuery === 'string' ? searchQuery : ''
  }

  function getPluginLabel (moduleName: string) {
    return pluginNameMap.value.get(moduleName) || moduleName
  }

  return {
    applyRouteFilters,
    getPluginLabel,
    nonSystemPlugins,
    pluginNameMap,
    pluginScopeTab,
    pluginSearch,
    systemPlugins,
    visiblePlugins,
  }
}
