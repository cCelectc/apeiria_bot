<template>
  <Card>
    <CardHeader>
      <CardTitle>AI Overview</CardTitle>
      <CardDescription>AI subsystem health and activity</CardDescription>
    </CardHeader>
    <CardContent>
      <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card v-for="m in metrics" :key="m.label">
          <CardHeader class="pb-2"><CardDescription>{{ m.label }}</CardDescription></CardHeader>
          <CardContent><div class="text-2xl font-bold">{{ m.value }}</div></CardContent>
        </Card>
      </div>
      <div class="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Quick Actions</CardTitle></CardHeader>
          <CardContent class="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" as-child>
              <RouterLink to="/ai/models">Manage Models</RouterLink>
            </Button>
            <Button variant="outline" size="sm" as-child>
              <RouterLink to="/ai/sessions">View Sessions</RouterLink>
            </Button>
            <Button variant="outline" size="sm" as-child>
              <RouterLink to="/ai/debug">Debug Traces</RouterLink>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Recent Activity</CardTitle></CardHeader>
          <CardContent>
            <EmptyState title="No recent activity" description="AI sessions will appear here." />
          </CardContent>
        </Card>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { RouterLink } from "vue-router"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import Button from "@/components/ui/button/Button.vue"
import EmptyState from "@/components/EmptyState.vue"

const metrics = computed(() => [
  { label: "Status", value: "Active" },
  { label: "Sessions", value: "-" },
  { label: "Memories", value: "-" },
  { label: "Documents", value: "-" },
])
</script>
