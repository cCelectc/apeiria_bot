<script setup lang="ts">
import { AlertCircle } from '@lucide/vue'
import { Button } from '@/components/ui/button'

defineProps<{ message?: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
    <div class="flex items-center gap-2">
      <AlertCircle class="size-4 text-destructive" aria-hidden="true" />
      <p class="text-sm font-medium text-destructive">{{ $t('error.loadFailed') }}</p>
    </div>
    <p v-if="message" class="mt-1 text-sm text-destructive/80">{{ message }}</p>
    <Button variant="outline" size="sm" class="mt-2" @click="$emit('retry')">
      {{ $t('error.retry') }}
    </Button>
  </div>
</template>
