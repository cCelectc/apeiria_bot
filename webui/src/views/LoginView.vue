<script setup lang="ts">
import { reactive } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useLoginMutation } from '@/composables/useAuth'

const form = reactive({ username: 'admin', password: '' })
const { mutate, isPending, isError } = useLoginMutation()

function onSubmit() {
  mutate({ username: form.username, password: form.password })
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-muted/40 p-4">
    <Card class="w-full max-w-sm">
      <CardHeader class="text-center">
        <div
          class="mx-auto mb-2 flex size-12 items-center justify-center rounded-xl bg-primary text-xl font-bold text-primary-foreground"
        >
          A
        </div>
        <CardTitle class="text-2xl">{{ $t('login.title') }}</CardTitle>
        <CardDescription>{{ $t('login.subtitle') }}</CardDescription>
      </CardHeader>
      <CardContent>
        <form class="space-y-4" @submit.prevent="onSubmit">
          <div class="space-y-2">
            <Label for="username">{{ $t('login.username') }}</Label>
            <Input
              id="username"
              v-model="form.username"
              autocomplete="username"
              required
            />
          </div>
          <div class="space-y-2">
            <Label for="password">{{ $t('login.password') }}</Label>
            <Input
              id="password"
              v-model="form.password"
              type="password"
              autocomplete="current-password"
              required
            />
          </div>
          <p v-if="isError" class="text-sm text-destructive">
            {{ $t('login.error') }}
          </p>
          <Button type="submit" class="w-full" :disabled="isPending">
            {{ isPending ? $t('common.loading') : $t('login.submit') }}
          </Button>
        </form>
      </CardContent>
    </Card>
  </div>
</template>
