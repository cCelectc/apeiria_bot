import type { PluginItem, PluginReadmeResponse } from '@/api/plugins'
import type { PluginTranslate } from '@/utils/pluginDisplay'
import { computed, ref } from 'vue'
import { getErrorMessage } from '@/api/client'
import { getPluginReadme } from '@/api/plugins'

export function usePluginReadmeDialog(t: PluginTranslate) {
  const readmeDialogVisible = ref(false)
  const readmeLoading = ref(false)
  const readmeLoadingModule = ref('')
  const readmeTarget = ref<PluginItem | null>(null)
  const readmeDocument = ref<PluginReadmeResponse | null>(null)
  const readmeRenderedHtml = ref('')
  const readmeErrorMessage = ref('')

  const readmeDialogTitle = computed(() =>
    t('plugins.readmeTitle', {
      name: readmeTarget.value?.name || readmeTarget.value?.module_name || '',
    }),
  )
  const readmeFilename = computed(() => readmeDocument.value?.filename || '')
  const readmeHtml = computed(() => readmeRenderedHtml.value)

  async function openReadme(item: PluginItem) {
    if (!item.can_view_readme) {
      return
    }
    readmeTarget.value = item
    readmeDialogVisible.value = true
    readmeLoading.value = true
    readmeLoadingModule.value = item.module_name
    readmeDocument.value = null
    readmeRenderedHtml.value = ''
    readmeErrorMessage.value = ''
    try {
      const [readmeResponse, readmeRenderer] = await Promise.all([
        getPluginReadme(item.module_name),
        import('@/utils/readme'),
      ])
      readmeDocument.value = readmeResponse.data
      readmeRenderedHtml.value = readmeRenderer.renderReadmeHtml(
        readmeResponse.data.content,
        item.module_name,
      )
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
