<script setup lang="ts">
import { reactive } from 'vue'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useChangePasswordMutation } from '@/composables/useAuth'

const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const { mutate, isPending } = useChangePasswordMutation()

function onSubmit() {
  if (form.newPassword !== form.confirm) {
    toast.error('两次输入的新密码不一致')
    return
  }
  mutate(
    { old_password: form.oldPassword, new_password: form.newPassword },
    {
      onSuccess: () => {
        toast.success('密码已修改')
        form.oldPassword = ''
        form.newPassword = ''
        form.confirm = ''
      },
      onError: (e: Error) => toast.error(e.message || '修改失败'),
    },
  )
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <h1 class="text-2xl font-semibold tracking-tight">账号</h1>
    <p class="mb-6 mt-1 text-sm text-muted-foreground">修改管理员密码</p>
    <Card class="max-w-md">
      <CardHeader>
        <CardTitle class="text-base">修改密码</CardTitle>
      </CardHeader>
      <CardContent>
        <form class="space-y-4" @submit.prevent="onSubmit">
          <div class="space-y-2">
            <Label for="old">当前密码</Label>
            <Input id="old" v-model="form.oldPassword" type="password" required />
          </div>
          <div class="space-y-2">
            <Label for="new">新密码</Label>
            <Input id="new" v-model="form.newPassword" type="password" required />
          </div>
          <div class="space-y-2">
            <Label for="confirm">确认新密码</Label>
            <Input id="confirm" v-model="form.confirm" type="password" required />
          </div>
          <Button type="submit" :disabled="isPending">保存</Button>
        </form>
      </CardContent>
    </Card>
  </div>
</template>
