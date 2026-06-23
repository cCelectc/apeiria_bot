<template>
  <CommandDialog :open="open" @update:open="open = $event">
    <CommandInput placeholder="Search pages and actions..." />
    <CommandList>
      <CommandEmpty>No results found.</CommandEmpty>
      <CommandGroup heading="Pages">
        <CommandItem
          v-for="item in pages"
          :key="item.to"
          :value="item.label"
          @select="navigate(item.to)"
        >
          <component :is="item.icon" class="size-4" />
          {{ item.label }}
          <CommandShortcut>{{ item.shortcut }}</CommandShortcut>
        </CommandItem>
      </CommandGroup>
    </CommandList>
  </CommandDialog>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue"
import { useRouter } from "vue-router"
import {
  Gauge, Settings, Plug, Store, Cable, Shield, Users,
  Brain, Cpu, MessageSquare, BookOpen, UserCircle, Bug,
  Terminal, RefreshCw,
} from "@lucide/vue"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command"

const router = useRouter()
const open = ref(false)

const pages = [
  { label: "Dashboard", to: "/dashboard", icon: Gauge, shortcut: "D" },
  { label: "Core Settings", to: "/config/core", icon: Settings, shortcut: "C" },
  { label: "Plugins", to: "/config/plugins", icon: Plug, shortcut: "P" },
  { label: "Store", to: "/config/store", icon: Store, shortcut: "" },
  { label: "Adapters", to: "/config/adapters", icon: Cable, shortcut: "" },
  { label: "Permissions", to: "/config/permissions", icon: Shield, shortcut: "" },
  { label: "Accounts", to: "/config/accounts", icon: Users, shortcut: "" },
  { label: "AI Overview", to: "/ai/overview", icon: Brain, shortcut: "" },
  { label: "AI Models", to: "/ai/models", icon: Cpu, shortcut: "M" },
  { label: "AI Sessions", to: "/ai/sessions", icon: MessageSquare, shortcut: "S" },
  { label: "AI Memories", to: "/ai/memories", icon: Brain, shortcut: "" },
  { label: "AI Knowledge", to: "/ai/knowledge", icon: BookOpen, shortcut: "" },
  { label: "AI Personas", to: "/ai/personas", icon: UserCircle, shortcut: "" },
  { label: "AI Debug", to: "/ai/debug", icon: Bug, shortcut: "" },
  { label: "Chat", to: "/ops/chat", icon: MessageSquare, shortcut: "T" },
  { label: "Logs", to: "/ops/logs", icon: Terminal, shortcut: "L" },
  { label: "Update", to: "/ops/update", icon: RefreshCw, shortcut: "U" },
]

function navigate(to: string) {
  open.value = false
  router.push(to)
}

function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault()
    open.value = !open.value
  }
}

onMounted(() => window.addEventListener("keydown", onKeydown))
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown))
</script>
