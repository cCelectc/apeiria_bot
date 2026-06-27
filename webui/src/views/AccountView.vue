<script setup lang="ts">
import { reactive } from "vue";
import { useI18n } from "vue-i18n";
import { AlertCircle } from "@lucide/vue";
import { toast } from "vue-sonner";
import PageHeader from "@/components/PageHeader.vue";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useChangePasswordMutation } from "@/composables/useAuth";

const form = reactive({ oldPassword: "", newPassword: "", confirm: "" });
const { t } = useI18n();
const { mutate, isPending, isError, error, reset } =
  useChangePasswordMutation();

function onSubmit() {
  if (form.newPassword !== form.confirm) {
    toast.error(t("account.passwordMismatch"));
    return;
  }
  mutate(
    { old_password: form.oldPassword, new_password: form.newPassword },
    {
      onSuccess: () => {
        toast.success(t("account.success"));
        form.oldPassword = "";
        form.newPassword = "";
        form.confirm = "";
      },
      onError: (e: Error) =>
        toast.error(e.message || t("account.changeFailed")),
    },
  );
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <PageHeader
      :title="$t('account.title')"
      :subtitle="$t('account.description')"
    />
    <Card class="max-w-md">
      <CardHeader>
        <CardTitle class="text-base">{{
          $t("account.changePassword")
        }}</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          v-if="isError"
          class="mb-4 rounded-lg border border-destructive/50 bg-destructive/10 p-4"
        >
          <div class="flex items-center gap-2">
            <AlertCircle class="size-4 text-destructive" />
            <p class="text-sm font-medium text-destructive">
              {{ $t("account.operationFailed") }}
            </p>
          </div>
          <p class="mt-1 text-sm text-destructive/80">
            {{ (error as Error)?.message }}
          </p>
          <Button
            variant="outline"
            size="sm"
            class="mt-2"
            @click="() => reset()"
            >{{ $t("error.retry") }}</Button
          >
        </div>
        <form class="space-y-4" @submit.prevent="onSubmit">
          <div class="space-y-2">
            <Label for="old">{{ $t("account.oldPassword") }}</Label>
            <Input
              id="old"
              v-model="form.oldPassword"
              type="password"
              required
            />
          </div>
          <div class="space-y-2">
            <Label for="new">{{ $t("account.newPassword") }}</Label>
            <Input
              id="new"
              v-model="form.newPassword"
              type="password"
              required
            />
          </div>
          <div class="space-y-2">
            <Label for="confirm">{{ $t("account.confirmPassword") }}</Label>
            <Input
              id="confirm"
              v-model="form.confirm"
              type="password"
              required
            />
          </div>
          <Button type="submit" :disabled="isPending">{{
            $t("common.save")
          }}</Button>
        </form>
      </CardContent>
    </Card>
  </div>
</template>
