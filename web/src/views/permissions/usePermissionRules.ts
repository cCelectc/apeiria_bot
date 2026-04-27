import type { AccessRuleItem } from '@/api/access'
import type { PluginTranslate } from '@/views/plugins/display'
import { ref, type Ref } from 'vue'
import {
  createAccessRule,
  deleteAccessRule,
} from '@/api/access'
import { getErrorMessage } from '@/api/client'
import { ruleKey } from '@/views/permissions/filters'

interface NoticeStoreLike {
  show: (
    message: string,
    color?: 'success' | 'error' | 'warning' | 'info',
  ) => void
}

export function usePermissionRules (options: {
  errorMessage: Ref<string>
  noticeStore: NoticeStoreLike
  rules: Ref<AccessRuleItem[]>
  t: PluginTranslate
}) {
  const creatingRule = ref(false)

  async function createRule (payload: {
    subject_type: string
    subject_id: string
    plugin_module: string
    effect: string
    note: string | null
  }): Promise<void> {
    creatingRule.value = true
    options.errorMessage.value = ''
    try {
      const response = await createAccessRule(payload)
      options.rules.value = [
        response.data,
        ...options.rules.value.filter(item => ruleKey(item) !== ruleKey(response.data)),
      ]
      options.noticeStore.show(options.t('permissions.ruleCreated'), 'success')
    } catch (error) {
      options.errorMessage.value = getErrorMessage(
        error,
        options.t('permissions.ruleCreateFailed'),
      )
      options.noticeStore.show(options.errorMessage.value, 'error')
    } finally {
      creatingRule.value = false
    }
  }

  async function handleDeleteRule (rule: AccessRuleItem): Promise<void> {
    options.errorMessage.value = ''
    try {
      await deleteAccessRule({
        subject_type: rule.subject_type,
        subject_id: rule.subject_id,
        plugin_module: rule.plugin_module,
      })
      options.rules.value = options.rules.value.filter(item => ruleKey(item) !== ruleKey(rule))
      options.noticeStore.show(options.t('permissions.ruleDeleted'), 'success')
    } catch (error) {
      options.errorMessage.value = getErrorMessage(
        error,
        options.t('permissions.ruleDeleteFailed'),
      )
      options.noticeStore.show(options.errorMessage.value, 'error')
    }
  }

  return {
    createRule,
    creatingRule,
    handleDeleteRule,
  }
}
