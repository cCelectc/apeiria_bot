<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronsUpDown,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Monitor,
  Moon,
  Plug,
  Puzzle,
  ScrollText,
  Settings,
  Store,
  Sun,
} from '@lucide/vue'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { useAuthStore } from '@/stores/auth'
import { type Theme, useUiStore } from '@/stores/ui'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const auth = useAuthStore()

const nav = [
  { name: 'dashboard', label: '看板', icon: LayoutDashboard },
  { name: 'plugins', label: '插件', icon: Puzzle },
  { name: 'adapters', label: '适配器', icon: Plug },
  { name: 'store', label: '商店', icon: Store },
  { name: 'config', label: '配置', icon: Settings },
  { name: 'logs', label: '日志', icon: ScrollText },
]

const currentLabel = computed(
  () => nav.find((n) => n.name === route.name)?.label ?? '',
)

const initial = computed(() => (auth.username ?? 'A').slice(0, 1).toUpperCase())

function setTheme(t: Theme) {
  ui.setTheme(t)
}

function logout() {
  auth.clearSession()
  void router.push({ name: 'login' })
}
</script>

<template>
  <SidebarProvider>
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div class="flex items-center gap-2 px-1 py-1.5">
          <div
            class="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary font-bold text-primary-foreground"
          >
            A
          </div>
          <span class="text-base font-semibold group-data-[collapsible=icon]:hidden">
            Apeiria
          </span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem v-for="item in nav" :key="item.name">
                <SidebarMenuButton
                  as-child
                  :is-active="route.name === item.name"
                  :tooltip="item.label"
                >
                  <RouterLink :to="{ name: item.name }">
                    <component :is="item.icon" />
                    <span>{{ item.label }}</span>
                  </RouterLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <SidebarMenuButton size="lg">
                  <Avatar class="size-8 rounded-lg">
                    <AvatarFallback class="rounded-lg bg-primary/10 text-primary">
                      {{ initial }}
                    </AvatarFallback>
                  </Avatar>
                  <div class="grid flex-1 text-left text-sm leading-tight">
                    <span class="truncate font-medium">{{ auth.username ?? '管理员' }}</span>
                  </div>
                  <ChevronsUpDown class="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" class="w-56">
                <DropdownMenuLabel>{{ auth.username ?? '管理员' }}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem @click="router.push({ name: 'account' })">
                  <KeyRound class="size-4" />
                  修改密码
                </DropdownMenuItem>
                <DropdownMenuItem @click="logout">
                  <LogOut class="size-4" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>

    <SidebarInset>
      <header
        class="flex h-16 shrink-0 items-center gap-2 border-b bg-card/60 px-4 backdrop-blur"
      >
        <SidebarTrigger class="-ml-1" />
        <div class="h-4 w-px bg-border" />
        <h1 class="text-sm font-medium">{{ currentLabel }}</h1>
        <div class="ml-auto flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="ghost" size="icon">
                <Sun v-if="ui.theme === 'light'" class="size-4" />
                <Moon v-else-if="ui.theme === 'dark'" class="size-4" />
                <Monitor v-else class="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem @click="setTheme('light')">
                <Sun class="size-4" />
                亮色
              </DropdownMenuItem>
              <DropdownMenuItem @click="setTheme('dark')">
                <Moon class="size-4" />
                暗色
              </DropdownMenuItem>
              <DropdownMenuItem @click="setTheme('system')">
                <Monitor class="size-4" />
                跟随系统
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <main class="min-h-0 flex-1 overflow-auto">
        <RouterView />
      </main>
    </SidebarInset>
  </SidebarProvider>
</template>
