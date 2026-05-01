<template>
  <section
    class="workbench-split-pane"
    :class="{
      'workbench-split-pane--full-height': fullHeight,
      'workbench-split-pane--wide-sidebar': wideSidebar,
    }"
  >
    <aside class="workbench-split-pane__sidebar">
      <slot name="sidebar" />
    </aside>

    <main class="workbench-split-pane__main">
      <slot />
    </main>
  </section>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    fullHeight?: boolean
    wideSidebar?: boolean
  }>(), {
    fullHeight: false,
    wideSidebar: false,
  })
</script>

<style scoped>
.workbench-split-pane {
  display: grid;
  grid-template-columns: var(--workbench-sidebar-width, 300px) minmax(0, 1fr);
  gap: 14px;
  min-width: 0;
}

.workbench-split-pane--wide-sidebar {
  grid-template-columns: minmax(320px, 360px) minmax(0, 1fr);
}

.workbench-split-pane--full-height {
  min-height: 0;
  flex: 1 1 auto;
  overflow: hidden;
}

.workbench-split-pane__sidebar,
.workbench-split-pane__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.workbench-split-pane--full-height .workbench-split-pane__sidebar,
.workbench-split-pane--full-height .workbench-split-pane__main {
  overflow: hidden;
}

.workbench-split-pane--full-height .workbench-split-pane__sidebar :deep(> *),
.workbench-split-pane--full-height .workbench-split-pane__main :deep(> *) {
  min-height: 0;
  flex: 1 1 auto;
}

@media (max-width: 980px) {
  .workbench-split-pane,
  .workbench-split-pane--wide-sidebar {
    grid-template-columns: minmax(0, 1fr);
  }

  .workbench-split-pane--full-height {
    overflow: visible;
  }

  .workbench-split-pane--full-height .workbench-split-pane__sidebar,
  .workbench-split-pane--full-height .workbench-split-pane__main {
    overflow: visible;
  }

  .workbench-split-pane--full-height .workbench-split-pane__sidebar :deep(> *),
  .workbench-split-pane--full-height .workbench-split-pane__main :deep(> *) {
    flex: 0 1 auto;
  }
}
</style>
