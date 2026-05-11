<template>
  <TooltipProvider>
    <div v-if="!authStore.isReady" class="app-loading">
      {{ t('common.loading') }}
    </div>
    <RouterView v-else />
    <Transition name="notice">
      <div
        v-if="noticeStore.visible"
        class="notice"
        :class="noticeToneClass()"
        role="status"
        @click="noticeStore.hide()"
      >
        {{ noticeStore.message }}
      </div>
    </Transition>
  </TooltipProvider>
</template>

<script setup lang="ts">
import { computed, onMounted, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNoticeStore } from '@/stores/notice'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const { t, locale } = useI18n()
const authStore = useAuthStore()
const noticeStore = useNoticeStore()
const themeStore = useThemeStore()

const documentTitle = computed(() => {
  const titleKey = typeof route.meta.titleKey === 'string' ? route.meta.titleKey : ''
  if (!titleKey) {
    return t('layout.defaultTitle')
  }
  return t('layout.pageTitle', { page: t(titleKey) })
})

watchEffect(() => {
  document.title = documentTitle.value
  document.documentElement.lang = locale.value === 'zh_CN' ? 'zh-CN' : 'en-US'
  themeStore.applyTheme()
})

onMounted(async () => {
  await authStore.initialize()
})

function noticeToneClass() {
  return {
    'notice--error': noticeStore.color === 'error',
    'notice--success': noticeStore.color === 'success',
    'notice--warning': noticeStore.color === 'warning',
    'notice--info': noticeStore.color === 'info',
  }
}
</script>
