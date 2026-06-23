<template>
  <Card>
    <CardHeader>
      <CardTitle>WebUI Build</CardTitle>
      <CardDescription>
        {{ status.is_built ? (status.is_stale ? "Stale" : "Up to date") : "Not built" }}
      </CardDescription>
    </CardHeader>
    <CardContent>
      <div class="flex flex-col gap-3">
        <Button
          variant="outline"
          :disabled="!status.can_build || building"
          @click="startBuild"
        >
          <Spinner v-if="building" data-icon="inline-start" class="size-4" />
          {{ building ? "Building..." : "Rebuild WebUI" }}
        </Button>
        <pre
          v-if="buildLog"
          class="max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs font-mono"
        >{{ buildLog }}</pre>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { dashboardService, type WebUIBuildStatus } from "@/api/services/dashboard"
import Button from "@/components/ui/button/Button.vue"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"

const props = defineProps<{ status: WebUIBuildStatus }>()

const building = ref(false)
const buildLog = ref("")

async function startBuild() {
  building.value = true
  buildLog.value = ""
  try {
    await dashboardService.streamRebuildWebUI((evt) => {
      if (evt.event === "chunk" && evt.chunk) {
        buildLog.value += evt.chunk
      }
    })
  } catch {
    buildLog.value += "\n[Build failed]"
  } finally {
    building.value = false
  }
}
</script>
