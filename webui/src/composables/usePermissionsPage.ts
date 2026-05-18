import type { AccessRuleItem } from '@/api/access'
import type { PluginItem } from '@/api/plugins'
import { computed, reactive, ref } from 'vue'
import {
  createAccessRule,
  deleteAccessRule,
  getAccessRules,
  normalizeAccessRulesResponse,
  updatePluginAccessMode,
} from '@/api/access'
import { getErrorMessage } from '@/api/client'
import { getPlugins, normalizePluginsResponse } from '@/api/plugins'
import { useNoticeStore } from '@/stores/notice'
import {
  filteredRules,
  manageablePlugins,
  pluginModuleOptions,
  pluginRuleCount as countPluginRules,
  ruleKey,
  type RuleEffectFilter,
  visiblePlugins as filterVisiblePlugins,
} from '@/utils/permissions'

export function usePermissionsPage(t: (key: string, params?: Record<string, unknown>) => string) {
  const noticeStore = useNoticeStore()
  const loading = ref(false)
  const errorMessage = ref('')
  const plugins = ref<PluginItem[]>([])
  const rules = ref<AccessRuleItem[]>([])
  const creatingRule = ref(false)
  const pendingPluginAccessMode = ref(false)
  const pluginSearch = ref('')
  const ruleSearch = ref('')
  const ruleEffectFilter = ref<RuleEffectFilter>('__all__')
  const selectedPluginModule = ref('')
  const pluginRuleForm = reactive({
    subject_type: 'user',
    subject_id: '',
    effect: 'allow',
    note: '',
  })

  const manageablePluginItems = computed(() => manageablePlugins(plugins.value))
  const visiblePluginItems = computed(() =>
    filterVisiblePlugins(manageablePluginItems.value, pluginSearch.value),
  )
  const moduleOptions = computed(() => pluginModuleOptions(manageablePluginItems.value))
  const selectedPlugin = computed(() =>
    manageablePluginItems.value.find(
      item => item.module_name === selectedPluginModule.value,
    ) || null,
  )
  const selectedPluginRules = computed(() =>
    rules.value.filter(rule => rule.plugin_module === selectedPluginModule.value),
  )
  const selectedPluginUserAllowRules = computed(() =>
    selectedPluginRules.value.filter(
      rule => rule.subject_type === 'user' && rule.effect === 'allow',
    ),
  )
  const selectedPluginUserDenyRules = computed(() =>
    selectedPluginRules.value.filter(
      rule => rule.subject_type === 'user' && rule.effect === 'deny',
    ),
  )
  const selectedPluginGroupAllowRules = computed(() =>
    selectedPluginRules.value.filter(
      rule => rule.subject_type === 'group' && rule.effect === 'allow',
    ),
  )
  const selectedPluginGroupDenyRules = computed(() =>
    selectedPluginRules.value.filter(
      rule => rule.subject_type === 'group' && rule.effect === 'deny',
    ),
  )
  const filteredRuleItems = computed(() =>
    filteredRules(rules.value, {
      effect: ruleEffectFilter.value,
      search: ruleSearch.value,
    }),
  )

  function ensureSelections() {
    if (!selectedPluginModule.value && manageablePluginItems.value.length > 0) {
      selectedPluginModule.value = manageablePluginItems.value[0].module_name
    }
    if (
      selectedPluginModule.value
      && !manageablePluginItems.value.some(
        item => item.module_name === selectedPluginModule.value,
      )
    ) {
      selectedPluginModule.value = manageablePluginItems.value[0]?.module_name || ''
    }
  }

  function pluginRuleCount(moduleName: string) {
    return countPluginRules(rules.value, moduleName)
  }

  async function loadAll() {
    loading.value = true
    errorMessage.value = ''
    try {
      const [pluginsResponse, rulesResponse] = await Promise.all([
        getPlugins(),
        getAccessRules(),
      ])
      plugins.value = normalizePluginsResponse(pluginsResponse.data)
      rules.value = normalizeAccessRulesResponse(rulesResponse.data)
      ensureSelections()
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('permissions.loadFailed'))
    } finally {
      loading.value = false
    }
  }

  async function createRule(payload: {
    subject_type: string
    subject_id: string
    plugin_module: string
    effect: string
    note: string | null
  }): Promise<boolean> {
    if (!payload.subject_id.trim() || !payload.plugin_module.trim()) {
      noticeStore.show(t('permissions.ruleFieldsRequired'), 'warning')
      return false
    }
    creatingRule.value = true
    errorMessage.value = ''
    try {
      const response = await createAccessRule(payload)
      rules.value = [
        response.data,
        ...rules.value.filter(item => ruleKey(item) !== ruleKey(response.data)),
      ]
      noticeStore.show(t('permissions.ruleCreated'), 'success')
      ensureSelections()
      return true
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('permissions.ruleCreateFailed'))
      noticeStore.show(errorMessage.value, 'error')
      return false
    } finally {
      creatingRule.value = false
    }
  }

  async function createRuleForPlugin() {
    if (!selectedPluginModule.value) {
      return
    }
    const created = await createRule({
      subject_type: pluginRuleForm.subject_type,
      subject_id: pluginRuleForm.subject_id.trim(),
      plugin_module: selectedPluginModule.value,
      effect: pluginRuleForm.effect,
      note: pluginRuleForm.note.trim() || null,
    })
    if (created) {
      pluginRuleForm.subject_id = ''
      pluginRuleForm.note = ''
      pluginRuleForm.effect = 'allow'
    }
  }

  async function handleDeleteRule(rule: AccessRuleItem) {
    errorMessage.value = ''
    try {
      await deleteAccessRule({
        subject_type: rule.subject_type,
        subject_id: rule.subject_id,
        plugin_module: rule.plugin_module,
      })
      rules.value = rules.value.filter(item => ruleKey(item) !== ruleKey(rule))
      noticeStore.show(t('permissions.ruleDeleted'), 'success')
      ensureSelections()
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('permissions.ruleDeleteFailed'))
      noticeStore.show(errorMessage.value, 'error')
    }
  }

  async function updateSelectedPluginAccessMode(nextValue: unknown) {
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
    errorMessage.value = ''
    try {
      await updatePluginAccessMode(selectedPlugin.value.module_name, accessMode)
      noticeStore.show(t('common.save'), 'success')
    } catch (error) {
      selectedPlugin.value.access_mode = previous
      errorMessage.value = getErrorMessage(error, t('permissions.loadFailed'))
      noticeStore.show(errorMessage.value, 'error')
    } finally {
      pendingPluginAccessMode.value = false
    }
  }

  return {
    createRuleForPlugin,
    creatingRule,
    errorMessage,
    filteredRuleItems,
    handleDeleteRule,
    loadAll,
    loading,
    manageablePluginItems,
    moduleOptions,
    pendingPluginAccessMode,
    pluginRuleCount,
    pluginRuleForm,
    pluginSearch,
    plugins,
    ruleEffectFilter,
    ruleSearch,
    rules,
    selectedPlugin,
    selectedPluginGroupAllowRules,
    selectedPluginGroupDenyRules,
    selectedPluginModule,
    selectedPluginRules,
    selectedPluginUserAllowRules,
    selectedPluginUserDenyRules,
    updateSelectedPluginAccessMode,
    visiblePluginItems,
  }
}
