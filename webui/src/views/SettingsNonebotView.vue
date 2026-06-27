<script setup lang="ts">
import { computed, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import ConfigEditor from '@/components/ConfigEditor.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useConfigSchema,
  useNonebotConfig,
  useSaveNonebotConfig,
} from '@/composables/useSettings'

const {
  data: schema,
  isLoading: schemaLoading,
  isError: schemaError,
  error: schemaErrorDetail,
  refetch: schemaRefetch,
} = useConfigSchema('nonebot')
const {
  data: config,
  isLoading: configLoading,
  isError: configError,
  error: configErrorDetail,
  refetch: configRefetch,
} = useNonebotConfig()
const save = useSaveNonebotConfig()

const isError = computed(() => schemaError.value || configError.value)
const errorDetail = computed(
  () => (schemaErrorDetail.value || configErrorDetail.value) as Error | null,
)
const refetchAll = () => {
  schemaRefetch()
  configRefetch()
}

const editor = ref<InstanceType<typeof ConfigEditor>>()

onBeforeRouteLeave(async () => {
  if (editor.value && !(await editor.value.attemptClose())) return false
  return true
})
</script>

<template>
  <div class="flex min-h-0 flex-col p-6 lg:p-8 h-full">
    <PageHeader :title="$t('settings.nonebotTitle')" />
    <Card class="flex flex-col min-h-0 flex-1">
      <CardContent class="flex-1 min-h-0 overflow-auto">
        <ErrorState v-if="isError" class="mb-4" :message="(errorDetail as Error)?.message" @retry="refetchAll" />
        <Skeleton v-else-if="schemaLoading || configLoading" class="h-96" />
        <ConfigEditor
          v-else-if="schema && config"
          ref="editor"
          :schema="schema"
          :model-value="config"
          section="nonebot"
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
