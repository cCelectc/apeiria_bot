<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
        <DialogDescription v-if="description">{{ description }}</DialogDescription>
      </DialogHeader>
      <div class="flex flex-col gap-3">
        <div v-for="(step, i) in steps" :key="i" class="flex items-center gap-3">
          <Spinner v-if="step.status === 'running'" class="size-4" />
          <CheckCircle v-else-if="step.status === 'done'" class="size-4 text-emerald-500" />
          <XCircle v-else-if="step.status === 'failed'" class="size-4 text-destructive" />
          <Circle v-else class="size-4 text-muted-foreground" />
          <span
            class="text-sm"
            :class="{
              'text-muted-foreground': step.status === 'pending',
              'text-destructive': step.status === 'failed',
            }"
          >
            {{ step.label }}
          </span>
        </div>
      </div>
      <DialogFooter>
        <Button
          variant="outline"
          :disabled="!allowClose"
          @click="$emit('update:open', false)"
        >
          {{ done ? 'Close' : 'Cancel' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { CheckCircle, Circle, XCircle } from "@lucide/vue"
import Button from "@/components/ui/button/Button.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import DialogContent from "@/components/ui/dialog/DialogContent.vue"
import DialogDescription from "@/components/ui/dialog/DialogDescription.vue"
import DialogFooter from "@/components/ui/dialog/DialogFooter.vue"
import DialogHeader from "@/components/ui/dialog/DialogHeader.vue"
import DialogTitle from "@/components/ui/dialog/DialogTitle.vue"

export interface TaskStep {
  label: string
  status: "pending" | "running" | "done" | "failed"
}

const props = defineProps<{
  open: boolean
  title: string
  description?: string
  steps: TaskStep[]
}>()

defineEmits<{
  "update:open": [value: boolean]
}>()

const done = computed(() => props.steps.every((s) => s.status === "done"))
const allowClose = computed(() => props.steps.every((s) => s.status !== "running"))
</script>
