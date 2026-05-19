<script setup lang="ts">
withDefaults(defineProps<{
  fullHeight?: boolean
  wideSidebar?: boolean
}>(), {
  fullHeight: false,
  wideSidebar: false,
})
</script>

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

    <section class="workbench-split-pane__main">
      <slot />
    </section>
  </section>
</template>
