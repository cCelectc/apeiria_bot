<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cn } from "@/lib/utils"
import { Separator } from "@/components/ui/separator"

const props = defineProps<{
  class?: HTMLAttributes["class"]
}>()
</script>

<template>
  <div
    data-slot="sidebar-separator"
    data-sidebar="separator"
    :class="cn('px-2', props.class)"
  >
    <Separator class="bg-sidebar-border">
      <slot />
    </Separator>
  </div>
</template>
