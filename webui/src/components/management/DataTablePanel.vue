<script setup lang="ts">
import type { WorkbenchTableColumn } from './types'
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import EmptyState from './EmptyState.vue'
import Panel from './Panel.vue'
import LoadingSkeleton from './LoadingSkeleton.vue'

withDefaults(defineProps<{
  columns?: WorkbenchTableColumn[]
  emptyText?: string
  emptyTitle?: string
  loading?: boolean
  subtitle?: string
  title?: string
}>(), {
  columns: () => [],
  emptyText: '',
  emptyTitle: '',
  loading: false,
  subtitle: '',
  title: '',
})
</script>

<template>
  <Panel class="workbench-data-panel" :subtitle="subtitle" :title="title">
    <template v-if="$slots.actions" #actions>
      <slot name="actions" />
    </template>

    <LoadingSkeleton v-if="loading" rows="6" />
    <EmptyState
      v-else-if="emptyTitle"
      :text="emptyText"
      :title="emptyTitle"
    />
    <Table v-else>
      <TableHeader v-if="columns.length">
        <TableRow>
          <TableHead
            v-for="column in columns"
            :key="column.key"
            :class="column.align ? `text-${column.align}` : undefined"
          >
            {{ column.label }}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <slot />
      </TableBody>
    </Table>
  </Panel>
</template>
