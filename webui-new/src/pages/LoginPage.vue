<template>
  <div class="flex min-h-[100dvh] items-center justify-center bg-muted/50">
    <Card class="w-full max-w-md overflow-hidden">
      <div class="h-1.5 bg-primary" />
      <CardHeader class="text-center">
        <CardTitle class="text-2xl">Apeiria</CardTitle>
        <CardDescription>Sign in to the admin panel</CardDescription>
      </CardHeader>
      <CardContent>
        <form class="flex flex-col gap-4" @submit.prevent="handleSubmit">
          <div class="flex flex-col gap-2">
            <Label for="username">Username</Label>
            <Input
              id="username"
              v-model="username"
              placeholder="admin"
              :disabled="submitting"
              :aria-invalid="!!error"
              @input="error = ''"
            />
          </div>
          <div class="flex flex-col gap-2">
            <Label for="password">Password</Label>
            <Input
              id="password"
              v-model="password"
              type="password"
              placeholder="Password"
              :disabled="submitting"
              :aria-invalid="!!error"
              @input="error = ''"
            />
          </div>
          <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
          <Button type="submit" class="w-full" :disabled="submitting">
            <Spinner v-if="submitting" data-icon="inline-start" class="size-4" />
            Sign in
          </Button>
        </form>
      </CardContent>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { useRouter, useRoute } from "vue-router"
import { authService } from "@/api/services/auth"
import { useAuthStore } from "@/stores/auth"
import { getApiErrorMessage } from "@/api/client"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Label from "@/components/ui/label/Label.vue"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const username = ref("")
const password = ref("")
const error = ref("")
const submitting = ref(false)

async function handleSubmit() {
  error.value = ""
  submitting.value = true
  try {
    const principal = await authService.login(username.value, password.value)
    auth.acceptSession(principal)
    const redirect = (route.query.redirect as string) || "/dashboard"
    router.push(redirect)
  } catch (err) {
    error.value = getApiErrorMessage(err, "Login failed")
  } finally {
    submitting.value = false
  }
}
</script>
