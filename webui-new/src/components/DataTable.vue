<template>
  <div class="rounded-md border">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead v-for="col in columns" :key="col.key" :class="col.class">
            {{ col.label }}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-if="loading">
          <TableCell :colspan="columns.length" class="p-8 text-center">
            <Skeleton class="h-8 w-full" />
          </TableCell>
        </TableRow>
        <TableRow v-else-if="rows.length === 0">
          <TableCell :colspan="columns.length" class="p-8 text-center">
            <Empty v-if="emptyTitle" :title="emptyTitle" />
            <span v-else class="text-sm text-muted-foreground">No data</span>
          </TableCell>
        </TableRow>
        <TableRow v-for="(row, i) in rows" :key="i" class="even:bg-muted/30 hover:bg-muted/50">
          <TableCell v-for="col in columns" :key="col.key" :class="col.class">
            <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key as keyof typeof row]">
              {{ row[col.key as keyof typeof row] }}
            </slot>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>

<script setup lang="ts">
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"

export interface ColumnDef {
  key: string
  label: string
  class?: string
}

defineProps<{
  columns: ColumnDef[]
  rows: Record<string, unknown>[]
  loading?: boolean
  emptyTitle?: string
}>()
</script>
