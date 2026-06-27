<script setup lang="ts">
import { ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import ConfigEditor from '@/components/ConfigEditor.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  useConfigSchema,
  useNonebotConfig,
  useApeiriaConfig,
  useSaveNonebotConfig,
  useSaveApeiriaConfig,
} from '@/composables/useSettings'

const { data: nonebotSchema, isLoading: nsLoading } = useConfigSchema('nonebot')
const { data: nonebotConfig, isLoading: ncLoading } = useNonebotConfig()
const saveNonebot = useSaveNonebotConfig()

const { data: apeiriaSchema, isLoading: asLoading } = useConfigSchema('apeiria')
const { data: apeiriaConfig, isLoading: acLoading } = useApeiriaConfig()
const saveApeiria = useSaveApeiriaConfig()

const nonebotEditor = ref<InstanceType<typeof ConfigEditor>>()
const apeiriaEditor = ref<InstanceType<typeof ConfigEditor>>()

onBeforeRouteLeave(async () => {
  for (const editor of [nonebotEditor.value, apeiriaEditor.value]) {
    if (editor && !(await editor.attemptClose())) return false
  }
  return true
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <h1 class="text-2xl font-semibold tracking-tight mb-6">设置</h1>

    <Tabs default-value="nonebot" class="w-full">
      <TabsList class="mb-6">
        <TabsTrigger value="nonebot">NoneBot</TabsTrigger>
        <TabsTrigger value="apeiria">Apeiria</TabsTrigger>
      </TabsList>

      <TabsContent value="nonebot">
        <Skeleton v-if="nsLoading || ncLoading" class="h-96" />
        <ConfigEditor
          v-else-if="nonebotSchema && nonebotConfig"
          ref="nonebotEditor"
          :schema="nonebotSchema"
          :model-value="nonebotConfig"
          section="nonebot"
          :save-mutation="
            async (d: Record<string, unknown>) => {
              await saveNonebot.mutateAsync(d)
            }
          "
        />
      </TabsContent>

      <TabsContent value="apeiria">
        <Skeleton v-if="asLoading || acLoading" class="h-96" />
        <ConfigEditor
          v-else-if="apeiriaSchema && apeiriaConfig"
          ref="apeiriaEditor"
          :schema="apeiriaSchema"
          :model-value="apeiriaConfig"
          section="apeiria"
          :save-mutation="
            async (d: Record<string, unknown>) => {
              await saveApeiria.mutateAsync(d)
            }
          "
        />
      </TabsContent>
    </Tabs>
  </div>
</template>
