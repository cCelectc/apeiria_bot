<template>
  <Sidebar collapsible="icon">
    <SidebarHeader>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton size="lg" as-child>
            <RouterLink to="/">
              <div class="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Bot class="size-4" />
              </div>
              <div class="flex flex-col gap-0.5 leading-none">
                <span class="font-semibold">Apeiria</span>
                <span class="text-xs text-muted-foreground">Admin</span>
              </div>
            </RouterLink>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarHeader>

    <SidebarContent>
      <SidebarGroup v-for="group in navGroups" :key="group.id">
        <SidebarGroupLabel>{{ group.label }}</SidebarGroupLabel>
        <SidebarMenu>
          <template v-for="item in group.children" :key="item.id">
            <SidebarMenuItem v-if="isLeaf(item)">
              <SidebarMenuButton
                as-child
                :is-active="isActive(item.to)"
              >
                <RouterLink :to="item.to">
                  <component :is="item.icon" />
                  <span>{{ item.label }}</span>
                </RouterLink>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <Collapsible
              v-else-if="isParent(item)"
              v-model:open="expandedGroups[item.id]"
              :key="item.id"
              as-child
            >
              <SidebarMenuItem>
                <CollapsibleTrigger as-child>
                  <SidebarMenuButton
                    :is-active="isActiveParent(item)"
                  >
                    <component :is="item.icon" />
                    <span>{{ item.label }}</span>
                    <ChevronRight
                      class="ml-auto size-4 transition-transform duration-200"
                      :class="{ 'rotate-90': expandedGroups[item.id] }"
                    />
                  </SidebarMenuButton>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenuSub>
                    <SidebarMenuSubItem
                      v-for="child in item.children"
                      :key="child.id"
                    >
                      <SidebarMenuSubButton
                        as-child
                        :is-active="isActive(child.to!)"
                      >
                        <RouterLink :to="child.to!">
                          <component :is="child.icon" />
                          <span>{{ child.label }}</span>
                        </RouterLink>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>
          </template>
        </SidebarMenu>
      </SidebarGroup>
    </SidebarContent>

    <SidebarFooter>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton as-child>
            <ThemeToggle />
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarFooter>

    <SidebarRail />
  </Sidebar>
</template>

<script setup lang="ts">
import { reactive } from "vue"
import { useRoute, RouterLink } from "vue-router"
import {
  Bot,
  Gauge,
  Settings,
  Plug,
  Store,
  Cable,
  Shield,
  Users,
  Brain,
  Cpu,
  MessageSquare,
  BookOpen,
  UserCircle,
  Bug,
  Terminal,
  RefreshCw,
  ChevronRight,
  User,
  Heart,
  Sliders,
} from "@lucide/vue"
import type { Component } from "vue"
import ThemeToggle from "./ThemeToggle.vue"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

interface NavItem {
  id: string
  label: string
  icon: Component
  to?: string
  children?: NavItem[]
}

function isLeaf(item: NavItem): item is NavItem & { to: string } {
  return !item.children && item.to !== undefined
}

function isParent(item: NavItem): item is NavItem & { children: NavItem[] } {
  return item.children !== undefined
}

const navGroups: { id: string; label: string; children: NavItem[] }[] = [
  {
    id: "overview",
    label: "Overview",
    children: [
      { id: "dashboard", label: "Dashboard", icon: Gauge, to: "/dashboard" },
    ],
  },
  {
    id: "configuration",
    label: "Configuration",
    children: [
      { id: "core", label: "Core Settings", icon: Settings, to: "/config/core" },
      { id: "plugins", label: "Plugins", icon: Plug, to: "/config/plugins" },
      { id: "store", label: "Store", icon: Store, to: "/config/store" },
      { id: "adapters", label: "Adapters", icon: Cable, to: "/config/adapters" },
      { id: "permissions", label: "Permissions", icon: Shield, to: "/config/permissions" },
      { id: "accounts", label: "Accounts", icon: Users, to: "/config/accounts" },
    ],
  },
  {
    id: "ai",
    label: "AI Studio",
    children: [
      {
        id: "ai-studio",
        label: "AI Studio",
        icon: Brain,
        children: [
          { id: "ai-overview", label: "Overview", icon: Gauge, to: "/ai/overview" },
          { id: "ai-models", label: "Models", icon: Cpu, to: "/ai/models" },
          { id: "ai-sessions", label: "Sessions", icon: MessageSquare, to: "/ai/sessions" },
          { id: "ai-memories", label: "Memories", icon: Brain, to: "/ai/memories" },
          { id: "ai-knowledge", label: "Knowledge", icon: BookOpen, to: "/ai/knowledge" },
          { id: "ai-personas", label: "Personas", icon: UserCircle, to: "/ai/personas" },
          { id: "ai-profiles", label: "Profiles", icon: User, to: "/ai/profiles" },
          { id: "ai-relationships", label: "Relationships", icon: Heart, to: "/ai/relationships" },
          { id: "ai-runtime", label: "Runtime", icon: Sliders, to: "/ai/runtime" },
          { id: "ai-debug", label: "Debug", icon: Bug, to: "/ai/debug" },
        ],
      },
    ],
  },
  {
    id: "operations",
    label: "Operations",
    children: [
      { id: "chat", label: "Chat", icon: MessageSquare, to: "/ops/chat" },
      { id: "logs", label: "Logs", icon: Terminal, to: "/ops/logs" },
      { id: "update", label: "Update", icon: RefreshCw, to: "/ops/update" },
    ],
  },
]

const expandedGroups = reactive<Record<string, boolean>>({
  "ai-studio": true,
})

const route = useRoute()

function isActive(to: string): boolean {
  if (to === "/dashboard") return route.path === "/dashboard" || route.path === "/"
  return route.path.startsWith(to)
}

function isActiveParent(item: NavItem): boolean {
  if (!item.children) return false
  return item.children.some((c) => route.path.startsWith(c.to ?? ""))
}
</script>
