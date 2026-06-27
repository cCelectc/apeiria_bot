<script setup lang="ts">
import { computed, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { AlertCircle } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import ConfigEditor from '@/components/ConfigEditor.vue'
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
  schemaRefetch.value()
  configRefetch.value()
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
    <h1 class="mb-6 text-2xl font-semibold tracking-tight">Apeiria 设置</h1>
    <Card class="flex flex-col min-h-0 flex-1">
      <CardContent class="flex-1 min-h-0 overflow-auto">
        <div v-if="isError" class="mb-4 rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <div class="flex items-center gap-2">
            <AlertCircle class="size-4 text-destructive" />
            <p class="text-sm font-medium text-destructive">加载失败</p>
          </div>
          <p class="mt-1 text-sm text-destructive/80">{{ errorDetail }}</p>
          <Button variant="outline" size="sm" class="mt-2" @click="refetchAll">重试</Button>
        </div>
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
