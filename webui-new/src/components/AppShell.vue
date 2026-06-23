<template>
  <SidebarProvider>
    <SidebarNav />
    <main class="flex min-h-[100dvh] w-full flex-col">
      <header class="sticky top-0 z-10 flex h-16 items-center gap-4 border-b bg-background px-6">
        <SidebarTrigger />
        <Separator orientation="vertical" class="h-6" />
        <BreadcrumbNav class="flex-1" />
        <slot name="header-actions" />
      </header>
      <div class="flex-1 p-6">
        <RouterView />
      </div>
    </main>
  </SidebarProvider>
</template>

<script setup lang="ts">
import { RouterView } from "vue-router"
import SidebarNav from "@/components/SidebarNav.vue"
import BreadcrumbNav from "@/components/BreadcrumbNav.vue"
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import Separator from "@/components/ui/separator/Separator.vue"
</script>
