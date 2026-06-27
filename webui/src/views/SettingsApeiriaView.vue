<script setup lang="ts">
import { computed, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import ConfigEditor from '@/components/ConfigEditor.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useApeiriaConfig,
  useConfigSchema,
  useSaveApeiriaConfig,
} from '@/composables/useSettings'

const {
  data: schema,
  isLoading: schemaLoading,
  isError: schemaIsError,
  error: schemaError,
  refetch: schemaRefetch,
} = useConfigSchema('apeiria')
const {
  data: config,
  isLoading: configLoading,
  isError: configIsError,
  error: configError,
  refetch: configRefetch,
} = useApeiriaConfig()

const isError = computed(() => schemaIsError.value || configIsError.value)
const errorDetail = computed(() => {
  if (schemaIsError.value) return (schemaError.value as Error)?.message
  if (configIsError.value) return (configError.value as Error)?.message
  return ''
})
const refetchAll = () => {
  schemaRefetch()
  configRefetch()
}
const save = useSaveApeiriaConfig()

const editor = ref<InstanceType<typeof ConfigEditor>>()

onBeforeRouteLeave(async () => {
  if (editor.value && !(await editor.value.attemptClose())) return false
  return true
})
</script>

<template>
  <div class="flex min-h-0 flex-col p-6 lg:p-8 h-full">
    <PageHeader :title="$t('settings.apeiriaTitle')" />
    <Card class="flex flex-col min-h-0 flex-1">
      <CardContent class="flex-1 min-h-0 overflow-auto">
        <ErrorState v-if="isError" class="mb-4" :message="errorDetail" @retry="refetchAll" />
        <Skeleton v-else-if="schemaLoading || configLoading" class="h-96" />
        <ConfigEditor
          v-else-if="schema && config"
          ref="editor"
          :schema="schema"
          :model-value="config"
          section="apeiria"
          :save-mutation="
            async (d: Record<string, unknown>) => {
              await save.mutateAsync(d)
            }
          "
        />
      </CardContent>
    </Card>
  </div>
</template>
