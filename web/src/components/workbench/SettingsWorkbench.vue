<template>
  <section class="workbench-settings">
    <header v-if="title || $slots.actions" class="workbench-settings__header">
      <div class="workbench-settings__heading">
        <div v-if="title" class="workbench-settings__title">{{ title }}</div>
        <div v-if="subtitle" class="workbench-settings__subtitle">{{ subtitle }}</div>
      </div>

      <div v-if="$slots.actions" class="workbench-settings__actions">
        <slot name="actions" />
      </div>
    </header>

    <v-alert
      v-if="restartHint"
      density="comfortable"
      type="warning"
      variant="tonal"
    >
      {{ restartHint }}
    </v-alert>

    <slot />
  </section>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    title?: string
    subtitle?: string
    restartHint?: string
  }>(), {
    restartHint: '',
    subtitle: '',
    title: '',
  })
</script>

<style scoped>
.workbench-settings {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 14px;
}

.workbench-settings__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.workbench-settings__heading {
  min-width: 0;
}

.workbench-settings__title {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 720;
  line-height: 1.35;
}

.workbench-settings__subtitle {
  max-width: 64ch;
  margin-top: 4px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.88rem;
  line-height: 1.5;
}

.workbench-settings__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}
</style>
