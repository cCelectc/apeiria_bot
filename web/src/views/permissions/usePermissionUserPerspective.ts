import type {
  AccessRuleItem,
  UserLevelItem,
} from '@/api/access'
import type { PluginTranslate } from '@/views/plugins/display'
import { computed, reactive, ref, type Ref } from 'vue'
import { updateUserLevel } from '@/api/access'
import { getErrorMessage } from '@/api/client'
import {
  userEntries as buildUserEntries,
  visibleUserEntries as filterVisibleUserEntries,
} from '@/views/permissions/filters'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

export function usePermissionUserPerspective (options: {
  createRule: (payload: {
    subject_type: string
    subject_id: string
    plugin_module: string
    effect: string
    note: string | null
  }) => Promise<void>
  errorMessage: Ref<string>
  noticeStore: NoticeStoreLike
  rules: Ref<AccessRuleItem[]>
  t: PluginTranslate
  users: Ref<UserLevelItem[]>
}) {
  const pendingUserKey = ref('')
  const userSearch = ref('')
  const selectedUserId = ref('')
  const userRuleForm = reactive({
    plugin_module: '',
    effect: 'allow',
    note: '',
  })

  const userEntries = computed(() =>
    buildUserEntries(options.users.value, options.rules.value),
  )
  const visibleUserEntries = computed(() =>
    filterVisibleUserEntries(userEntries.value, userSearch.value),
  )
  const selectedUserRules = computed(() =>
    options.rules.value.filter(rule => rule.subject_type === 'user' && rule.subject_id === selectedUserId.value),
  )
  const selectedUserLevels = computed(() =>
    options.users.value.filter(item => item.user_id === selectedUserId.value),
  )

  function ensureUserSelection (): void {
    if (!selectedUserId.value && userEntries.value.length > 0) {
      selectedUserId.value = userEntries.value[0].user_id
    }
  }

  async function createRuleForUser (): Promise<void> {
    if (!selectedUserId.value || !userRuleForm.plugin_module.trim()) {
      return
    }
    await options.createRule({
      subject_type: 'user',
      subject_id: selectedUserId.value,
      plugin_module: userRuleForm.plugin_module.trim(),
      effect: userRuleForm.effect,
      note: userRuleForm.note.trim() || null,
    })
    userRuleForm.plugin_module = ''
    userRuleForm.note = ''
    userRuleForm.effect = 'allow'
  }

  async function updateLevel (item: UserLevelItem, nextValue: unknown): Promise<void> {
    const level = Number(nextValue)
    if (Number.isNaN(level) || level === item.level) {
      return
    }
    const previous = item.level
    const key = `${item.user_id}:${item.group_id}`
    item.level = level
    pendingUserKey.value = key
    options.errorMessage.value = ''
    try {
      await updateUserLevel(item.user_id, item.group_id, level)
      options.noticeStore.show(
        options.t('permissions.levelUpdated', {
          groupId: item.group_id,
          userId: item.user_id,
        }),
        'success',
      )
    } catch (error) {
      item.level = previous
      options.errorMessage.value = getErrorMessage(
        error,
        options.t('permissions.levelUpdateFailed'),
      )
      options.noticeStore.show(options.errorMessage.value, 'error')
    } finally {
      pendingUserKey.value = ''
    }
  }

  return {
    createRuleForUser,
    ensureUserSelection,
    pendingUserKey,
    selectedUserId,
    selectedUserLevels,
    selectedUserRules,
    updateLevel,
    userEntries,
    userRuleForm,
    userSearch,
    visibleUserEntries,
  }
}
