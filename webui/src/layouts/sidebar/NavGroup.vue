<script setup lang="ts">
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import NavCollapse from "./NavCollapse.vue";
import NavItem from "./NavItem.vue";
import { isNavParent, type NavGroup } from "./sidebarNav";

defineProps<{ group: NavGroup }>();
</script>

<template>
  <SidebarGroup>
    <SidebarGroupLabel v-if="group.label">
      {{ $t(group.label) }}
    </SidebarGroupLabel>
    <SidebarGroupContent>
      <SidebarMenu>
        <SidebarMenuItem v-for="item in group.items" :key="item.title">
          <NavCollapse v-if="isNavParent(item)" :item="item" />
          <NavItem v-else :item="item" />
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroupContent>
  </SidebarGroup>
</template>
