<script setup lang="ts">
import { ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import ConfigEditor from '@/components/ConfigEditor.vue'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useApeiriaConfig,
  useConfigSchema,
  useSaveApeiriaConfig,
} from '@/composables/useSettings'

const { data: schema, isLoading: schemaLoading } = useConfigSchema('apeiria')
const { data: config, isLoading: configLoading } = useApeiriaConfig()
const save = useSaveApeiriaConfig()

const editor = ref<InstanceType<typeof ConfigEditor>>()

onBeforeRouteLeave(async () => {
  if (editor.value && !(await editor.value.attemptClose())) return false
  return true
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <h1 class="mb-6 text-2xl font-semibold tracking-tight">Apeiria 设置</h1>
    <Card>
      <CardContent class="p-6">
        <Skeleton v-if="schemaLoading || configLoading" class="h-96" />
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
