<template>
  <Empty>
    <EmptyMedia>
      <component :is="icon" class="size-12 text-muted-foreground" />
    </EmptyMedia>
    <EmptyHeader>
      <EmptyTitle>{{ title }}</EmptyTitle>
      <EmptyDescription v-if="description">{{ description }}</EmptyDescription>
    </EmptyHeader>
    <EmptyContent v-if="$slots.default">
      <slot />
    </EmptyContent>
    <EmptyContent v-if="$slots.actions">
      <slot name="actions" />
    </EmptyContent>
  </Empty>
</template>

<script setup lang="ts">
import { Inbox } from "@lucide/vue"
import type { Component } from "vue"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"

withDefaults(defineProps<{
  title: string
  description?: string
  icon?: Component
}>(), {
  icon: () => Inbox,
})
</script>
