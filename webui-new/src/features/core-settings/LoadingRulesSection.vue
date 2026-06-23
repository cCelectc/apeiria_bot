<template>
  <Card>
    <CardHeader>
      <CardTitle>Plugin Loading Rules</CardTitle>
      <CardDescription>Configure which plugin modules and directories to load</CardDescription>
    </CardHeader>
    <CardContent>
      <EmptyState title="Loading rules" description="Configure which plugin source directories and module paths to load at startup." />
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import EmptyState from "@/components/EmptyState.vue"
</script>
