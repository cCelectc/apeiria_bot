<script setup lang="ts">
import { computed } from "vue";
import { marked } from "marked";

const props = defineProps<{
  text?: string;
}>();

const html = computed(() => {
  if (!props.text) return "";
  return marked.parse(props.text) as string;
});
</script>

<template>
  <div v-if="text" class="markdown-body" v-html="html" />
</template>

<style scoped>
.markdown-body :deep(p) {
  margin: 0.25em 0;
}
.markdown-body :deep(p:first-child) {
  margin-top: 0;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown-body :deep(code) {
  background: hsl(var(--muted));
  border-radius: 0.25rem;
  padding: 0.1em 0.3em;
  font-size: 0.85em;
}
.markdown-body :deep(pre) {
  background: hsl(var(--muted));
  border-radius: 0.25rem;
  padding: 0.5em 0.75em;
  overflow-x: auto;
  font-size: 0.8rem;
  margin: 0.25em 0;
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.25em;
  margin: 0.25em 0;
}
.markdown-body :deep(a) {
  color: hsl(var(--primary));
  text-decoration: underline;
}
</style>
