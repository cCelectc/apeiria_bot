<script setup lang="ts">
import ConfigEditor from '@/components/ConfigEditor.vue'
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
</script>

<template>
  <div class="p-6 lg:p-8 space-y-8">
    <div>
      <h2 class="text-xl font-semibold mb-4">NoneBot 配置</h2>
      <Skeleton v-if="nsLoading || ncLoading" class="h-96" />
      <ConfigEditor
        v-else-if="nonebotSchema && nonebotConfig"
        :schema="nonebotSchema"
        :model-value="nonebotConfig"
        section="nonebot"
        :save-mutation="
          async (d: Record<string, unknown>) => {
            await saveNonebot.mutateAsync(d)
          }
        "
      />
    </div>

    <Separator />

    <div>
      <h2 class="text-xl font-semibold mb-4">Apeiria 配置</h2>
      <Skeleton v-if="asLoading || acLoading" class="h-96" />
      <ConfigEditor
        v-else-if="apeiriaSchema && apeiriaConfig"
        :schema="apeiriaSchema"
        :model-value="apeiriaConfig"
        section="apeiria"
        :save-mutation="
          async (d: Record<string, unknown>) => {
            await saveApeiria.mutateAsync(d)
          }
        "
      />
    </div>
  </div>
</template>
