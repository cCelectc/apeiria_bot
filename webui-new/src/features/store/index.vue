<template>
  <Card>
    <CardHeader>
      <CardTitle>Store</CardTitle>
      <CardDescription>Browse and install plugins and adapters</CardDescription>
    </CardHeader>
    <CardContent>
      <EmptyState title="Store" description="Plugin and adapter marketplace coming soon." />
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
