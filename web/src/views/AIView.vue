<template>
  <PageScaffold
    :subtitle="t('ai.pageSubtitle.overview')"
    :title="t('ai.title')"
  >
    <v-alert
      color="info"
      density="comfortable"
      variant="tonal"
    >
      {{ t('ai.redirectingToOverview') }}
    </v-alert>
  </PageScaffold>
</template>

<script setup lang="ts">
  import { onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { PageScaffold } from '@/components/workbench'

  const { t } = useI18n()
  const router = useRouter()

  onMounted(() => {
    void router.replace({ name: 'ai-overview' })
  })
</script>
