import type { PluginItem, PluginReadmeResponse } from '@/api/plugins'
import type { PluginTranslate } from '@/views/plugins/display'
import { computed, ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import { getPluginReadme } from '@/api/plugins'
import { renderReadmeHtml } from '@/views/plugins/readme'

export function usePluginReadmeDialog (t: PluginTranslate) {
  const readmeDialogVisible = ref(false)
  const readmeLoading = ref(false)
  const readmeLoadingModule = ref('')
  const readmeTarget = ref<PluginItem | null>(null)
  const readmeDocument = ref<PluginReadmeResponse | null>(null)
  const readmeErrorMessage = ref('')

  const readmeDialogTitle = computed(() =>
    t('plugins.readmeTitle', {
      name: readmeTarget.value?.name || readmeTarget.value?.module_name || '',
    }),
  )
  const readmeFilename = computed(() => readmeDocument.value?.filename || '')
  const readmeHtml = computed(() =>
    renderReadmeHtml(
      readmeDocument.value?.content || '',
      readmeTarget.value?.module_name,
    ),
  )

  async function openReadme (item: PluginItem) {
    readmeTarget.value = item
    readmeDialogVisible.value = true
    readmeLoading.value = true
    readmeLoadingModule.value = item.module_name
    readmeDocument.value = null
    readmeErrorMessage.value = ''
    try {
      readmeDocument.value = (await getPluginReadme(item.module_name)).data
    } catch (error) {
      readmeErrorMessage.value = getErrorMessage(error, t('plugins.readmeLoadFailed'))
    } finally {
      readmeLoading.value = false
      readmeLoadingModule.value = ''
    }
  }

  return {
    openReadme,
    readmeDialogTitle,
    readmeDialogVisible,
    readmeErrorMessage,
    readmeFilename,
    readmeHtml,
    readmeLoading,
    readmeLoadingModule,
    readmeTarget,
  }
}
