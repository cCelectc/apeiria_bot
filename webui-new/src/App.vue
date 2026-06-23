<template>
  <TooltipProvider>
    <RouterView />
    <CommandPalette />
    <Toaster />
  </TooltipProvider>
</template>

<script setup lang="ts">
import { RouterView } from "vue-router"
import { Toaster } from "vue-sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import CommandPalette from "@/components/CommandPalette.vue"
</script>
