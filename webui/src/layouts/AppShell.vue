<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
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
} from "@lucide/vue";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
} from "@/components/ui/sidebar";
import { useAuthStore } from "@/stores/auth";
import { type Theme, useUiStore } from "@/stores/ui";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const auth = useAuthStore();
const { t } = useI18n();

const nav = [
  { name: "dashboard", icon: LayoutDashboard },
  { name: "plugins", icon: Puzzle },
  { name: "adapters", icon: Plug },
  { name: "store", icon: Store },
  { name: "logs", icon: ScrollText },
];

const currentLabel = computed(() => {
  if (route.path.startsWith("/settings")) return t("nav.settings");
  if (route.name === "account") return t("nav.account");
  const item = nav.find((n) => n.name === route.name);
  return item ? t(`nav.${item.name}`) : "";
});

const initial = computed(() =>
  (auth.username ?? "A").slice(0, 1).toUpperCase(),
);

function setTheme(t: Theme) {
  ui.setTheme(t);
}

function cycleTheme() {
  const order: Theme[] = ["light", "dark", "system"];
  const idx = order.indexOf(ui.theme);
  setTheme(order[(idx + 1) % order.length]);
}

const themeName = computed(() => {
  const names: Record<Theme, string> = {
    light: t("theme.light"),
    dark: t("theme.dark"),
    system: t("theme.system"),
  };
  return names[ui.theme];
});

function logout() {
  auth.clearSession();
  void router.push({ name: "login" });
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
          <span
            class="text-base font-semibold group-data-[collapsible=icon]:hidden"
          >
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
                  :tooltip="$t(`nav.${item.name}`)"
                >
                  <RouterLink :to="{ name: item.name }">
                    <component :is="item.icon" />
                    <span>{{ $t(`nav.${item.name}`) }}</span>
                  </RouterLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup class="mt-auto">
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <DropdownMenu>
                  <DropdownMenuTrigger as-child>
                    <SidebarMenuButton
                      :is-active="route.path.startsWith('/settings')"
                      :tooltip="$t('nav.settings')"
                    >
                      <Settings class="size-4" />
                      <span>{{ $t("nav.settings") }}</span>
                    </SidebarMenuButton>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent side="right" align="start">
                    <DropdownMenuItem
                      @click="router.push({ name: 'settings-nonebot' })"
                    >
                      NoneBot
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      @click="router.push({ name: 'settings-apeiria' })"
                    >
                      Apeiria
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  as-child
                  :is-active="route.name === 'account'"
                  :tooltip="$t('nav.account')"
                >
                  <RouterLink :to="{ name: 'account' }">
                    <KeyRound class="size-4" />
                    <span>{{ $t("nav.account") }}</span>
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
                    <AvatarFallback
                      class="rounded-lg bg-primary/10 text-primary"
                    >
                      {{ initial }}
                    </AvatarFallback>
                  </Avatar>
                  <div class="grid flex-1 text-left text-sm leading-tight">
                    <span class="truncate font-medium">{{
                      auth.username ?? $t("account.admin")
                    }}</span>
                  </div>
                  <ChevronsUpDown class="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" class="w-56">
                <DropdownMenuLabel>{{
                  auth.username ?? $t("account.admin")
                }}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem @click="router.push({ name: 'account' })">
                  <KeyRound class="size-4" />
                  {{ $t("account.changePassword") }}
                </DropdownMenuItem>
                <DropdownMenuItem @click="logout">
                  <LogOut class="size-4" />
                  {{ $t("account.logout") }}
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
          <TooltipProvider :delay-duration="200">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  variant="ghost"
                  size="icon"
                  :aria-label="$t('theme.label')"
                  @click="cycleTheme"
                >
                  <Sun
                    v-if="ui.theme === 'light'"
                    class="size-4"
                    aria-hidden="true"
                  />
                  <Moon
                    v-else-if="ui.theme === 'dark'"
                    class="size-4"
                    aria-hidden="true"
                  />
                  <Monitor v-else class="size-4" aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{{ themeName }}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </header>
      <main class="min-h-0 flex-1 overflow-auto">
        <RouterView />
      </main>
    </SidebarInset>
  </SidebarProvider>
</template>
