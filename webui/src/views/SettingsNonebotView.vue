<script setup lang="ts">
import { computed, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { AlertCircle } from '@lucide/vue'
import ConfigEditor from '@/components/ConfigEditor.vue'
import { Button } from '@/components/ui/button'
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
    <h1 class="mb-6 text-2xl font-semibold tracking-tight">NoneBot 设置</h1>
    <Card class="flex flex-col min-h-0 flex-1">
      <CardContent class="flex-1 min-h-0 overflow-auto">
        <div v-if="isError" class="mb-4 rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <div class="flex items-center gap-2">
            <AlertCircle class="size-4 text-destructive" />
            <p class="text-sm font-medium text-destructive">加载失败</p>
          </div>
          <p class="mt-1 text-sm text-destructive/80">{{ (errorDetail as Error)?.message }}</p>
          <Button variant="outline" size="sm" class="mt-2" @click="refetchAll">重试</Button>
        </div>
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
