<template>
  <div class="flex flex-col gap-6">
    <Card>
      <CardHeader>
        <CardTitle>Core Settings</CardTitle>
        <CardDescription>Configure bot runtime parameters</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs v-model="activeTab" class="w-full">
          <TabsList>
            <TabsTrigger value="structured">Structured</TabsTrigger>
            <TabsTrigger value="raw">Raw TOML</TabsTrigger>
          </TabsList>
          <TabsContent value="structured" class="mt-4">
            <FeedbackAlert v-if="error" :message="error" variant="destructive" />
            <Skeleton v-if="loading" class="h-64 w-full" />
            <SettingsEditor
              v-if="fields && !loading"
              :fields="fields"
              :model-value="values"
              @update:model-value="onValuesChange"
            />
            <Button v-if="!loading" class="mt-4" :disabled="!dirty" @click="saveStructured">
              <Spinner v-if="saving" data-icon="inline-start" class="size-4" />
              Save
            </Button>
          </TabsContent>
          <TabsContent value="raw" class="mt-4">
            <MonacoEditor
              v-model="rawContent"
              language="toml"
              :style="{ height: '400px' }"
            />
            <div class="mt-2 flex items-center gap-2">
              <Button :disabled="!rawDirty" @click="saveRaw">
                <Spinner v-if="savingRaw" data-icon="inline-start" class="size-4" />
                Save
              </Button>
              <Button variant="outline" :disabled="!rawDirty" @click="validateRaw">
                Validate
              </Button>
              <span v-if="rawError" class="text-sm text-destructive">{{ rawError }}</span>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>

    <LoadingRulesSection />
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { useRequest } from "@/composables/useRequest"
import { coreService } from "@/api/services/core"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import Tabs from "@/components/ui/tabs/Tabs.vue"
import TabsContent from "@/components/ui/tabs/TabsContent.vue"
import TabsList from "@/components/ui/tabs/TabsList.vue"
import TabsTrigger from "@/components/ui/tabs/TabsTrigger.vue"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import FeedbackAlert from "@/components/FeedbackAlert.vue"
import SettingsEditor from "@/components/SettingsEditor.vue"
import MonacoEditor from "@/components/MonacoEditor.vue"
import LoadingRulesSection from "./LoadingRulesSection.vue"

const notice = useNoticeStore()
const activeTab = ref("structured")

const { data: settingsData, loading, error } = useRequest(
  "core-settings",
  () => coreService.getSettings(),
)

const fields = ref(settingsData.value?.fields ?? [])
const values = ref(settingsData.value?.values ?? {})
const dirty = ref(false)
const saving = ref(false)

const rawContent = ref("")
const rawOriginal = ref("")
const rawDirty = ref(false)
const rawError = ref("")
const savingRaw = ref(false)

function onValuesChange(v: Record<string, unknown>) {
  values.value = v
  dirty.value = true
}

async function saveStructured() {
  saving.value = true
  try {
    await coreService.updateSettings(values.value)
    dirty.value = false
    notice.markRestartPending()
    notice.show("Settings saved. Restart required to apply.", "info")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed to save"), "error")
  } finally {
    saving.value = false
  }
}

async function saveRaw() {
  savingRaw.value = true
  try {
    await coreService.updateRawSettings(rawContent.value)
    rawOriginal.value = rawContent.value
    notice.markRestartPending()
    notice.show("Raw settings saved.", "info")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed to save"), "error")
  } finally {
    savingRaw.value = false
  }
}

async function validateRaw() {
  rawError.value = ""
  try {
    await coreService.validateRawSettings(rawContent.value)
    notice.show("Settings valid.", "success")
  } catch (err) {
    rawError.value = getApiErrorMessage(err, "Validation failed")
  }
}
</script>
