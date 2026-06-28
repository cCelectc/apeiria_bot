<script setup lang="ts">
import { computed } from "vue";
import { ChevronRight } from "@lucide/vue";
import { useRoute, useRouter } from "vue-router";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenuButton,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar";
import type { NavParent } from "./sidebarNav";

const props = defineProps<{ item: NavParent }>();

const route = useRoute();
const router = useRouter();
const { state, isMobile } = useSidebar();

const expanded = computed(() => state.value === "expanded" || isMobile.value);
const isActive = computed(() =>
  props.item.children.some((child) => child.to.name === route.name),
);
</script>

<template>
  <Collapsible
    v-if="expanded"
    :default-open="isActive"
    class="group/collapsible"
  >
    <CollapsibleTrigger as-child>
      <SidebarMenuButton :is-active="isActive" :tooltip="$t(item.title)">
        <component :is="item.icon" />
        <span>{{ $t(item.title) }}</span>
        <ChevronRight
          class="ml-auto transition-transform group-data-[state=open]/collapsible:rotate-90"
        />
      </SidebarMenuButton>
    </CollapsibleTrigger>
    <CollapsibleContent>
      <SidebarMenuSub>
        <SidebarMenuSubItem
          v-for="child in item.children"
          :key="child.to.name"
        >
          <SidebarMenuSubButton
            as-child
            :is-active="route.name === child.to.name"
          >
            <RouterLink :to="child.to">
              <span>{{ $t(child.title) }}</span>
            </RouterLink>
          </SidebarMenuSubButton>
        </SidebarMenuSubItem>
      </SidebarMenuSub>
    </CollapsibleContent>
  </Collapsible>

  <DropdownMenu v-else>
    <DropdownMenuTrigger as-child>
      <SidebarMenuButton :is-active="isActive" :tooltip="$t(item.title)">
        <component :is="item.icon" />
        <span>{{ $t(item.title) }}</span>
      </SidebarMenuButton>
    </DropdownMenuTrigger>
    <DropdownMenuContent side="right" align="start">
      <DropdownMenuItem
        v-for="child in item.children"
        :key="child.to.name"
        :class="{
          'bg-accent text-accent-foreground': route.name === child.to.name,
        }"
        @click="router.push(child.to)"
      >
        {{ $t(child.title) }}
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
