<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { Button } from '@/components/ui/button'
import { EmptyState, PageScaffold, Panel, StatusBadge } from '@/components/management'

const route = useRoute()
const { t } = useI18n()

const title = computed(() => {
  const titleKey = typeof route.meta.titleKey === 'string' ? route.meta.titleKey : ''
  return titleKey ? t(titleKey) : t('layout.defaultTitle')
})
</script>

<template>
  <PageScaffold
    kicker="webui"
    :subtitle="t('webuiMigration.placeholderDescription')"
    :title="title"
  >
    <template #actions>
      <StatusBadge
        :label="t('common.loading')"
        tone="info"
      />
    </template>

    <Panel :title="title">
      <EmptyState
        :text="t('webuiMigration.placeholderBody')"
        :title="t('webuiMigration.placeholderTitle')"
      >
        <template #actions>
          <Button variant="secondary" @click="$router.back()">
            {{ t('common.cancel') }}
          </Button>
        </template>
      </EmptyState>
    </Panel>
  </PageScaffold>
</template>
