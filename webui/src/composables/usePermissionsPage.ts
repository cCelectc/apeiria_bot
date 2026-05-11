import type { AccessRuleItem, UserLevelItem } from '@/api/access'
import type { PluginItem } from '@/api/plugins'
import { computed, reactive, ref } from 'vue'
import {
  createAccessRule,
  deleteAccessRule,
  getAccessRules,
  getUsers,
  normalizeAccessRulesResponse,
  normalizeUserLevelsResponse,
  updatePluginAccessMode,
  updateUserLevel,
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
  userEntries as buildUserEntries,
  visiblePlugins as filterVisiblePlugins,
  visibleUserEntries as filterVisibleUserEntries,
} from '@/utils/permissions'

export function usePermissionsPage(t: (key: string, params?: Record<string, unknown>) => string) {
  const noticeStore = useNoticeStore()
  const loading = ref(false)
  const errorMessage = ref('')
  const plugins = ref<PluginItem[]>([])
  const rules = ref<AccessRuleItem[]>([])
  const users = ref<UserLevelItem[]>([])
  const creatingRule = ref(false)
  const pendingPluginAccessMode = ref(false)
  const pendingUserKey = ref('')
  const pluginSearch = ref('')
  const userSearch = ref('')
  const ruleSearch = ref('')
  const ruleEffectFilter = ref<RuleEffectFilter>('__all__')
  const selectedPluginModule = ref('')
  const selectedUserId = ref('')
  const pluginRuleForm = reactive({
    subject_type: 'user',
    subject_id: '',
    effect: 'allow',
    note: '',
  })
  const userRuleForm = reactive({
    plugin_module: '',
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
  const userEntryItems = computed(() => buildUserEntries(users.value, rules.value))
  const visibleUserEntryItems = computed(() =>
    filterVisibleUserEntries(userEntryItems.value, userSearch.value),
  )
  const selectedUserRules = computed(() =>
    rules.value.filter(
      rule => rule.subject_type === 'user' && rule.subject_id === selectedUserId.value,
    ),
  )
  const selectedUserLevels = computed(() =>
    users.value.filter(item => item.user_id === selectedUserId.value),
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
    if (!selectedUserId.value && userEntryItems.value.length > 0) {
      selectedUserId.value = userEntryItems.value[0].user_id
    }
    if (
      selectedUserId.value
      && !userEntryItems.value.some(item => item.user_id === selectedUserId.value)
    ) {
      selectedUserId.value = userEntryItems.value[0]?.user_id || ''
    }
  }

  function pluginRuleCount(moduleName: string) {
    return countPluginRules(rules.value, moduleName)
  }

  async function loadAll() {
    loading.value = true
    errorMessage.value = ''
    try {
      const [pluginsResponse, rulesResponse, usersResponse] = await Promise.all([
        getPlugins(),
        getAccessRules(),
        getUsers(),
      ])
      plugins.value = normalizePluginsResponse(pluginsResponse.data)
      rules.value = normalizeAccessRulesResponse(rulesResponse.data)
      users.value = normalizeUserLevelsResponse(usersResponse.data)
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

  async function createRuleForUser() {
    if (!selectedUserId.value) {
      return
    }
    const created = await createRule({
      subject_type: 'user',
      subject_id: selectedUserId.value,
      plugin_module: userRuleForm.plugin_module.trim(),
      effect: userRuleForm.effect,
      note: userRuleForm.note.trim() || null,
    })
    if (created) {
      userRuleForm.plugin_module = ''
      userRuleForm.note = ''
      userRuleForm.effect = 'allow'
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

  async function updateLevel(item: UserLevelItem, nextValue: unknown) {
    const level = Number(nextValue)
    if (Number.isNaN(level) || item.level === level) {
      return
    }
    const previous = item.level
    const key = `${item.user_id}:${item.group_id}`
    item.level = level
    pendingUserKey.value = key
    errorMessage.value = ''
    try {
      await updateUserLevel(item.user_id, item.group_id, level)
      noticeStore.show(
        t('permissions.levelUpdated', {
          groupId: item.group_id,
          userId: item.user_id,
        }),
        'success',
      )
    } catch (error) {
      item.level = previous
      errorMessage.value = getErrorMessage(error, t('permissions.levelUpdateFailed'))
      noticeStore.show(errorMessage.value, 'error')
    } finally {
      pendingUserKey.value = ''
    }
  }

  return {
    createRuleForPlugin,
    createRuleForUser,
    creatingRule,
    errorMessage,
    filteredRuleItems,
    handleDeleteRule,
    loadAll,
    loading,
    manageablePluginItems,
    moduleOptions,
    pendingPluginAccessMode,
    pendingUserKey,
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
    selectedUserId,
    selectedUserLevels,
    selectedUserRules,
    updateLevel,
    updateSelectedPluginAccessMode,
    userEntryItems,
    userRuleForm,
    userSearch,
    users,
    visiblePluginItems,
    visibleUserEntryItems,
  }
}
