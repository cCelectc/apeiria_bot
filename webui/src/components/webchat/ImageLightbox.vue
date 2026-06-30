<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ChevronLeft, ChevronRight, Maximize, Minimize, X } from "@lucide/vue";
import { DialogRoot, DialogPortal } from "reka-ui";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

const props = defineProps<{
  images: Array<{ url: string }>;
  initialIndex: number;
  open: boolean;
}>();

const emit = defineEmits<{
  (e: "update:open", v: boolean): void;
}>();

const MIN_SCALE = 0.25;
const DEFAULT_SCALE = 1;
const MAX_SCALE = 5;

const currentIndex = ref(0);
const userScale = ref(DEFAULT_SCALE);
const isDragging = ref(false);
const hasDragged = ref(false);
const dragStart = ref({ x: 0, y: 0 });
const dragStartTx = ref(0);
const dragStartTy = ref(0);
const containerRef = ref<HTMLDivElement | null>(null);
const imgRef = ref<HTMLImageElement | null>(null);
const containerWidth = ref(0);
const containerHeight = ref(0);
const imgReady = ref(false);

watch(
  () => props.open,
  (v) => {
    if (v) {
      currentIndex.value = Math.max(0, Math.min(props.initialIndex, props.images.length - 1));
      userScale.value = DEFAULT_SCALE;
      imgReady.value = false;
    }
  },
);

const currentImage = computed(() => props.images[currentIndex.value]);
const hasMultiple = computed(() => props.images.length > 1);

const fitScale = computed(() => {
  const img = imgRef.value;
  if (!img || !containerWidth.value || !containerHeight.value) return 1;
  const nw = img.naturalWidth || 1;
  const nh = img.naturalHeight || 1;
  if (nw < 2 && nh < 2) return 1;
  return Math.min(containerWidth.value / nw, containerHeight.value / nh);
});

function resetPan() {
  userScale.value = DEFAULT_SCALE;
  const img = imgRef.value as HTMLElement & { _tx?: number; _ty?: number };
  if (img) {
    img._tx = 0;
    img._ty = 0;
  }
  applyTransform();
}

function zoomToOriginal() {
  const fs = fitScale.value;
  if (fs <= 0) return;
  userScale.value = Math.min(MAX_SCALE, 1 / fs);
  const img = imgRef.value as HTMLElement & { _tx?: number; _ty?: number };
  if (img) {
    img._tx = 0;
    img._ty = 0;
  }
  applyTransform();
  clampPan();
}

const isAtOriginal = computed(() => {
  const fs = fitScale.value;
  return Math.abs(userScale.value - Math.min(MAX_SCALE, 1 / (fs || 1))) < 0.01;
});

watch(currentIndex, () => {
  userScale.value = DEFAULT_SCALE;
  imgReady.value = false;
  nextTick(() => updateContainerSize());
});

function updateContainerSize() {
  const el = containerRef.value;
  if (el) {
    containerWidth.value = el.clientWidth;
    containerHeight.value = el.clientHeight;
  }
  nextTick(() => clampPan());
}

function onImgLoad() {
  imgReady.value = true;
  updateContainerSize();
}

function prev() {
  if (currentIndex.value > 0) currentIndex.value--;
}
function next() {
  if (currentIndex.value < props.images.length - 1) currentIndex.value++;
}

function close() {
  emit("update:open", false);
}

function onWheel(e: WheelEvent) {
  e.preventDefault();
  const oldScale = userScale.value;
  const delta = e.deltaY > 0 ? -0.25 : 0.25;
  const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, oldScale + delta));
  if (newScale === oldScale) return;

  const container = containerRef.value;
  if (!container) return;
  const rect = container.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;

  const img = imgRef.value;
  if (!img) return;

  const ratio = newScale / oldScale;
  const dx = (mx - rect.width / 2) * (1 - ratio);
  const dy = (my - rect.height / 2) * (1 - ratio);

  const imgEl = imgRef.value as HTMLElement & { _tx?: number; _ty?: number };
  const oldTx = imgEl._tx ?? 0;
  const oldTy = imgEl._ty ?? 0;
  const newTx = oldTx * ratio + dx;
  const newTy = oldTy * ratio + dy;

  imgEl._tx = newTx;
  imgEl._ty = newTy;

  userScale.value = newScale;
  applyTransform();
}

function applyTransform() {
  const img = imgRef.value as HTMLElement & { _tx?: number; _ty?: number };
  if (!img) return;
  const tx = img._tx ?? 0;
  const ty = img._ty ?? 0;
  const fs = fitScale.value;
  img.style.transform = `translate(${tx}px, ${ty}px) scale(${fs * userScale.value})`;
  img.style.transformOrigin = "center center";
}

function clampPan() {
  const img = imgRef.value as HTMLImageElement & { _tx?: number; _ty?: number };
  if (!img) return;
  const cw = containerWidth.value;
  const ch = containerHeight.value;
  const iw = img.naturalWidth * fitScale.value * userScale.value;
  const ih = img.naturalHeight * fitScale.value * userScale.value;

  let maxTx: number;
  let maxTy: number;

  if (userScale.value < DEFAULT_SCALE) {
    maxTx = Math.max(0, (cw - iw * 0.8) / 2);
    maxTy = Math.max(0, (ch - ih * 0.8) / 2);
  } else {
    const margin = 0.15;
    maxTx = Math.max(0, (iw - cw) / 2 + cw * margin);
    maxTy = Math.max(0, (ih - ch) / 2 + ch * margin);
  }

  img._tx = Math.max(-maxTx, Math.min(maxTx, img._tx ?? 0));
  img._ty = Math.max(-maxTy, Math.min(maxTy, img._ty ?? 0));
  applyTransform();
}

function onMouseDown(e: MouseEvent) {
  isDragging.value = true;
  hasDragged.value = false;
  dragStart.value = { x: e.clientX, y: e.clientY };
  const img = imgRef.value as HTMLElement & { _tx?: number; _ty?: number };
  dragStartTx.value = img?._tx ?? 0;
  dragStartTy.value = img?._ty ?? 0;
  e.preventDefault();
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging.value) return;
  const dx = e.clientX - dragStart.value.x;
  const dy = e.clientY - dragStart.value.y;
  if (!hasDragged.value && Math.abs(dx) < 3 && Math.abs(dy) < 3) return;
  hasDragged.value = true;
  const img = imgRef.value as HTMLElement & { _tx?: number; _ty?: number };
  if (!img) return;
  img._tx = dragStartTx.value + dx;
  img._ty = dragStartTy.value + dy;
  applyTransform();
}

function onMouseUp() {
  if (!isDragging.value) return;
  isDragging.value = false;
  clampPan();
}

function onKeydown(e: KeyboardEvent) {
  switch (e.key) {
    case "Escape":
      close();
      break;
    case "ArrowLeft":
      prev();
      break;
    case "ArrowRight":
      next();
      break;
  }
}

onMounted(() => {
  window.addEventListener("keydown", onKeydown);
  window.addEventListener("resize", updateContainerSize);
  window.addEventListener("mouseup", onMouseUp);
});
onUnmounted(() => {
  window.removeEventListener("keydown", onKeydown);
  window.removeEventListener("resize", updateContainerSize);
  window.removeEventListener("mouseup", onMouseUp);
});
</script>

<template>
  <DialogRoot
    :open="open"
    @update:open="emit('update:open', $event)"
  >
    <DialogPortal>
      <template v-if="open">
        <div class="fixed inset-0 z-50 bg-black/90" />
        <div class="fixed inset-0 z-50 flex flex-col">
        <button
          class="absolute top-4 right-4 z-10 rounded-md p-2 text-white/70 hover:text-white hover:bg-white/10 transition-colors"
          @click="close"
        >
          <X class="size-6" />
        </button>

        <button
          v-if="hasMultiple"
          class="absolute left-4 top-1/2 z-10 -translate-y-1/2 rounded-md p-2 text-white/70 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-30 disabled:cursor-default"
          :disabled="currentIndex === 0"
          @click="prev"
        >
          <ChevronLeft class="size-8" />
        </button>
        <button
          v-if="hasMultiple"
          class="absolute right-4 top-1/2 z-10 -translate-y-1/2 rounded-md p-2 text-white/70 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-30 disabled:cursor-default"
          :disabled="currentIndex === images.length - 1"
          @click="next"
        >
          <ChevronRight class="size-8" />
        </button>

        <div
          ref="containerRef"
          class="flex-1 flex items-center justify-center min-h-0 w-full overflow-hidden p-20"
          :class="isDragging ? 'cursor-grabbing' : 'cursor-grab'"
          @wheel.prevent="onWheel"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseUp"
        >
          <img
            v-if="currentImage"
            ref="imgRef"
            :src="currentImage.url"
            :key="currentIndex"
            alt=""
            draggable="false"
            class="block select-none transition-opacity duration-150"
            :class="imgReady ? 'opacity-100' : 'opacity-0'"
            style="will-change: transform"
            @load="onImgLoad"
          />
        </div>

        <div
          v-if="hasMultiple"
          class="absolute bottom-4 left-1/2 -translate-x-1/2 text-white/60 text-sm"
        >
          {{ currentIndex + 1 }} / {{ images.length }}
        </div>

        <div class="absolute bottom-4 right-4 z-10 flex items-center gap-1">
          <button
            class="rounded-md p-2 text-white/60 hover:text-white hover:bg-white/10 transition-colors"
            :title="isAtOriginal ? t('webchat.lightbox.fitWindow') : t('webchat.lightbox.originalSize')"
            @click="isAtOriginal ? resetPan() : zoomToOriginal()"
          >
            <Minimize v-if="isAtOriginal" class="size-5" />
            <Maximize v-else class="size-5" />
          </button>
        </div>
      </div>
      </template>
    </DialogPortal>
  </DialogRoot>
</template>
