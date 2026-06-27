<script setup lang="ts">
import type { Component } from "vue";

defineProps<{ message: string; icon?: Component }>();
</script>

<template>
  <div
    class="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-10 text-center"
  >
    <component
      :is="icon"
      v-if="icon"
      class="size-6 text-muted-foreground"
      aria-hidden="true"
    />
    <p class="text-sm text-muted-foreground">{{ message }}</p>
  </div>
</template>
