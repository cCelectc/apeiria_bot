<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch } from "vue";
import { Toaster } from "@/components/ui/sonner";
import { useUiStore } from "@/stores/ui";

const ui = useUiStore();

function resolveActiveTheme(): "light" | "dark" {
  if (ui.theme !== "system") return ui.theme;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyTheme() {
  document.documentElement.classList.toggle(
    "dark",
    resolveActiveTheme() === "dark",
  );
}

let mq: MediaQueryList | null = null;

onMounted(() => {
  applyTheme();
  mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", applyTheme);
});

onBeforeUnmount(() => {
  mq?.removeEventListener("change", applyTheme);
});

watch(() => ui.theme, applyTheme);
</script>

<template>
  <RouterView />
  <Toaster position="top-center" rich-colors :theme="resolveActiveTheme()" />
</template>
