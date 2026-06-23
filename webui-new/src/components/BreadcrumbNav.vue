<template>
  <Breadcrumb>
    <BreadcrumbList>
      <BreadcrumbItem v-for="(crumb, i) in crumbs" :key="i">
        <BreadcrumbLink v-if="i < crumbs.length - 1" :to="crumb.to">
          {{ crumb.label }}
        </BreadcrumbLink>
        <BreadcrumbPage v-else>
          {{ crumb.label }}
        </BreadcrumbPage>
        <BreadcrumbSeparator v-if="i < crumbs.length - 1" />
      </BreadcrumbItem>
    </BreadcrumbList>
  </Breadcrumb>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

const route = useRoute()

interface Crumb {
  label: string
  to: string
}

const crumbs = computed<Crumb[]>(() => {
  const items: Crumb[] = []
  for (const matched of route.matched) {
    const label = (matched.meta?.title as string) || matched.name?.toString() || matched.path
    if (label && label !== "/") {
      items.push({ label, to: matched.path })
    }
  }
  return items
})
</script>
