import type { AccessRuleItem } from '@/api/access'
import type { PluginItem } from '@/api/plugins'
import type { PluginTranslate } from '@/views/plugins/display'
import { computed, reactive, ref, type Ref } from 'vue'
import { updatePluginAccessMode } from '@/api/access'
import { getErrorMessage } from '@/api/client'
import {
  pluginModuleOptions as buildPluginModuleOptions,
  pluginRuleCount as countPluginRules,
  visiblePlugins as filterVisiblePlugins,
  manageablePlugins as getManageablePlugins,
} from '@/views/permissions/filters'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

export function usePermissionPluginPerspective (options: {
  createRule: (payload: {
    subject_type: string
    subject_id: string
    plugin_module: string
    effect: string
    note: string | null
  }) => Promise<void>
  errorMessage: Ref<string>
  noticeStore: NoticeStoreLike
  plugins: Ref<PluginItem[]>
  rules: Ref<AccessRuleItem[]>
  t: PluginTranslate
}) {
  const pendingPluginAccessMode = ref(false)
  const pluginSearch = ref('')
  const selectedPluginModule = ref('')
  const pluginRuleForm = reactive({
    subject_type: 'user',
    subject_id: '',
    effect: 'allow',
    note: '',
  })

  const manageablePlugins = computed(() =>
    getManageablePlugins(options.plugins.value),
  )
  const pluginModuleOptions = computed(() =>
    buildPluginModuleOptions(manageablePlugins.value),
  )
  const visiblePlugins = computed(() =>
    filterVisiblePlugins(manageablePlugins.value, pluginSearch.value),
  )
  const selectedPlugin = computed(() =>
    manageablePlugins.value.find(item => item.module_name === selectedPluginModule.value) || null,
  )
  const selectedPluginRules = computed(() =>
    options.rules.value.filter(rule => rule.plugin_module === selectedPluginModule.value),
  )
  const selectedPluginUserAllowRules = computed(() =>
    selectedPluginRules.value.filter(rule => rule.subject_type === 'user' && rule.effect === 'allow'),
  )
  const selectedPluginUserDenyRules = computed(() =>
    selectedPluginRules.value.filter(rule => rule.subject_type === 'user' && rule.effect === 'deny'),
  )
  const selectedPluginGroupAllowRules = computed(() =>
    selectedPluginRules.value.filter(rule => rule.subject_type === 'group' && rule.effect === 'allow'),
  )
  const selectedPluginGroupDenyRules = computed(() =>
    selectedPluginRules.value.filter(rule => rule.subject_type === 'group' && rule.effect === 'deny'),
  )

  function pluginRuleCount (moduleName: string): number {
    return countPluginRules(options.rules.value, moduleName)
  }

  function ensurePluginSelection (): void {
    if (!selectedPluginModule.value && manageablePlugins.value.length > 0) {
      selectedPluginModule.value = manageablePlugins.value[0].module_name
    }
    if (
      selectedPluginModule.value
      && !manageablePlugins.value.some(item => item.module_name === selectedPluginModule.value)
    ) {
      selectedPluginModule.value = manageablePlugins.value[0]?.module_name || ''
    }
  }

  async function createRuleForPlugin (): Promise<void> {
    if (!selectedPluginModule.value || !pluginRuleForm.subject_id.trim()) {
      return
    }
    await options.createRule({
      subject_type: pluginRuleForm.subject_type,
      subject_id: pluginRuleForm.subject_id.trim(),
      plugin_module: selectedPluginModule.value,
      effect: pluginRuleForm.effect,
      note: pluginRuleForm.note.trim() || null,
    })
    pluginRuleForm.subject_id = ''
    pluginRuleForm.note = ''
    pluginRuleForm.effect = 'allow'
  }

  async function updateSelectedPluginAccessMode (
    nextValue: unknown,
  ): Promise<void> {
    if (!selectedPlugin.value) {
      return
    }
    const accessMode = String(nextValue)
    if (!['default_allow', 'default_deny'].includes(accessMode)) {
      return
    }
    if (selectedPlugin.value.access_mode === accessMode) {
      return
    }

    const previous = selectedPlugin.value.access_mode
    selectedPlugin.value.access_mode = accessMode
    pendingPluginAccessMode.value = true
    options.errorMessage.value = ''
    try {
      await updatePluginAccessMode(selectedPlugin.value.module_name, accessMode)
      options.noticeStore.show(options.t('common.save'), 'success')
    } catch (error) {
      selectedPlugin.value.access_mode = previous
      options.errorMessage.value = getErrorMessage(error, options.t('permissions.loadFailed'))
      options.noticeStore.show(options.errorMessage.value, 'error')
    } finally {
      pendingPluginAccessMode.value = false
    }
  }

  return {
    createRuleForPlugin,
    ensurePluginSelection,
    manageablePlugins,
    pendingPluginAccessMode,
    pluginModuleOptions,
    pluginRuleCount,
    pluginRuleForm,
    pluginSearch,
    selectedPlugin,
    selectedPluginGroupAllowRules,
    selectedPluginGroupDenyRules,
    selectedPluginModule,
    selectedPluginRules,
    selectedPluginUserAllowRules,
    selectedPluginUserDenyRules,
    updateSelectedPluginAccessMode,
    visiblePlugins,
  }
}
