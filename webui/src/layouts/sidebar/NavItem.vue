<script setup lang="ts">
import { useRoute } from "vue-router";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import type { NavLeaf } from "./sidebarNav";

defineProps<{ item: NavLeaf }>();

const route = useRoute();
</script>

<template>
  <SidebarMenuButton
    as-child
    :is-active="item.to != null && route.name === item.to.name"
    :tooltip="$t(item.title)"
  >
    <a
      v-if="item.external"
      :href="item.href"
      target="_blank"
      rel="noopener noreferrer"
    >
      <component :is="item.icon" />
      <span>{{ $t(item.title) }}</span>
    </a>
    <RouterLink v-else :to="item.to ?? '/'">
      <component :is="item.icon" />
      <span>{{ $t(item.title) }}</span>
    </RouterLink>
  </SidebarMenuButton>
</template>
