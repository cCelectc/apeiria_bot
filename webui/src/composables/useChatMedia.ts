import type { ImageSegment } from '@/types/chat'
import { computed, ref } from 'vue'

export function formatBytes(bytes: number) {
  if (bytes <= 0) {
    return ''
  }
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function estimateImageSize(segment: ImageSegment) {
  if (segment.base64) {
    const padding = segment.base64.endsWith('==')
      ? 2
      : (segment.base64.endsWith('=') ? 1 : 0)
    const bytes = Math.max(
      0,
      Math.floor(segment.base64.length * 3 / 4) - padding,
    )
    return formatBytes(bytes)
  }
  return ''
}

export function useProtectedChatAssets(options: {
  imageAlt: () => string
  openImagePreviewSource: (src: string, alt: string, sizeText?: string) => void
}) {
  const protectedAssetUrls = ref<Record<string, string>>({})
  const loadingProtectedAssets = new Set<string>()

  async function ensureProtectedAssetUrl(rawUrl: string) {
    if (protectedAssetUrls.value[rawUrl] || loadingProtectedAssets.has(rawUrl)) {
      return
    }
    const token = localStorage.getItem('token')
    if (!token) {
      return
    }

    loadingProtectedAssets.add(rawUrl)
    try {
      const response = await fetch(rawUrl, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok) {
        throw new Error(`Failed to load asset: ${response.status}`)
      }
      const blob = await response.blob()
      protectedAssetUrls.value = {
        ...protectedAssetUrls.value,
        [rawUrl]: URL.createObjectURL(blob),
      }
    } catch {
      protectedAssetUrls.value = { ...protectedAssetUrls.value }
    } finally {
      loadingProtectedAssets.delete(rawUrl)
    }
  }

  function revokeProtectedAssetUrls() {
    for (const url of Object.values(protectedAssetUrls.value)) {
      URL.revokeObjectURL(url)
    }
    protectedAssetUrls.value = {}
    loadingProtectedAssets.clear()
  }

  function resolveImageUrl(segment: ImageSegment) {
    if (segment.base64) {
      return `data:${segment.mime || 'image/png'};base64,${segment.base64}`
    }
    const rawUrl = segment.url
    if (!rawUrl) {
      return ''
    }
    if (!rawUrl.startsWith('/api/chat/assets/')) {
      return rawUrl
    }
    void ensureProtectedAssetUrl(rawUrl)
    return protectedAssetUrls.value[rawUrl] || ''
  }

  async function openImagePreview(segment: ImageSegment) {
    let src = resolveImageUrl(segment)
    if (!src && segment.url?.startsWith('/api/chat/assets/')) {
      await ensureProtectedAssetUrl(segment.url)
      src = protectedAssetUrls.value[segment.url] || ''
    }
    if (!src) {
      return
    }
    options.openImagePreviewSource(
      src,
      segment.alt || options.imageAlt(),
      estimateImageSize(segment),
    )
  }

  return {
    ensureProtectedAssetUrl,
    openImagePreview,
    protectedAssetUrls,
    resolveImageUrl,
    revokeProtectedAssetUrls,
  }
}

export function useChatImagePreview() {
  const imagePreviewVisible = ref(false)
  const imagePreviewSrc = ref('')
  const imagePreviewAlt = ref('')
  const previewScale = ref(1)
  const previewOffsetX = ref(0)
  const previewOffsetY = ref(0)
  const previewImageRef = ref<HTMLImageElement>()
  const previewWrapRef = ref<HTMLElement>()
  const previewBaseScale = ref(1)
  const previewImageNaturalWidth = ref(0)
  const previewImageNaturalHeight = ref(0)
  const previewImageSizeText = ref('')
  const isDraggingPreview = ref(false)
  const dragStartX = ref(0)
  const dragStartY = ref(0)
  const dragOriginX = ref(0)
  const dragOriginY = ref(0)

  const previewBounds = computed(() => {
    const img = previewImageRef.value
    const wrap = previewWrapRef.value
    if (!img || !wrap) {
      return { maxX: 0, maxY: 0 }
    }
    const scaledWidth = img.clientWidth * previewScale.value
    const scaledHeight = img.clientHeight * previewScale.value
    const maxX = Math.max(0, (scaledWidth - wrap.clientWidth) / 2)
    const maxY = Math.max(0, (scaledHeight - wrap.clientHeight) / 2)
    return { maxX, maxY }
  })
  const canDragPreview = computed(() =>
    previewBounds.value.maxX > 0 || previewBounds.value.maxY > 0,
  )
  const previewImageStyle = computed(() => ({
    cursor: isDraggingPreview.value
      ? 'grabbing'
      : (canDragPreview.value ? 'grab' : 'zoom-in'),
    transform: `translate(${previewOffsetX.value}px, ${previewOffsetY.value}px) scale(${previewScale.value})`,
    transformOrigin: 'center center',
  }))

  function openImagePreviewSource(src: string, alt: string, sizeText = '') {
    if (!src) {
      return
    }
    imagePreviewSrc.value = src
    imagePreviewAlt.value = alt
    previewImageNaturalWidth.value = 0
    previewImageNaturalHeight.value = 0
    previewImageSizeText.value = sizeText
    resetPreviewTransform()
    imagePreviewVisible.value = true
  }

  function closeImagePreview() {
    imagePreviewVisible.value = false
    imagePreviewSrc.value = ''
    stopImageDrag()
    resetPreviewTransform()
  }

  function resetPreviewTransform() {
    previewScale.value = previewBaseScale.value
    previewOffsetX.value = 0
    previewOffsetY.value = 0
  }

  function zoomInPreview() {
    setPreviewScale(previewScale.value + 0.2)
  }

  function zoomOutPreview() {
    setPreviewScale(previewScale.value - 0.2)
  }

  function handlePreviewWheel(event: WheelEvent) {
    setPreviewScale(previewScale.value + (event.deltaY < 0 ? 0.12 : -0.12))
  }

  function startImageDrag(event: MouseEvent) {
    if (event.button !== 0 || !canDragPreview.value) {
      return
    }
    event.preventDefault()
    isDraggingPreview.value = true
    dragStartX.value = event.clientX
    dragStartY.value = event.clientY
    dragOriginX.value = previewOffsetX.value
    dragOriginY.value = previewOffsetY.value
    window.addEventListener('mousemove', onImageDrag)
    window.addEventListener('mouseup', stopImageDrag)
    window.addEventListener('mouseleave', stopImageDrag)
    window.addEventListener('blur', stopImageDrag)
  }

  function onImageDrag(event: MouseEvent) {
    if (!isDraggingPreview.value) {
      return
    }
    event.preventDefault()
    previewOffsetX.value = dragOriginX.value + event.clientX - dragStartX.value
    previewOffsetY.value = dragOriginY.value + event.clientY - dragStartY.value
    clampPreviewOffset()
  }

  function stopImageDrag() {
    isDraggingPreview.value = false
    window.removeEventListener('mousemove', onImageDrag)
    window.removeEventListener('mouseup', stopImageDrag)
    window.removeEventListener('mouseleave', stopImageDrag)
    window.removeEventListener('blur', stopImageDrag)
  }

  function setPreviewScale(next: number) {
    previewScale.value = Math.min(5, Math.max(0.5, Number(next.toFixed(2))))
    clampPreviewOffset()
  }

  function clampPreviewOffset() {
    const { maxX, maxY } = previewBounds.value
    previewOffsetX.value = Math.min(maxX, Math.max(-maxX, previewOffsetX.value))
    previewOffsetY.value = Math.min(maxY, Math.max(-maxY, previewOffsetY.value))
  }

  function downloadPreviewImage() {
    if (!imagePreviewSrc.value) {
      return
    }
    const link = document.createElement('a')
    link.href = imagePreviewSrc.value
    link.download = 'chat-image.png'
    link.click()
  }

  function handlePreviewImageLoad() {
    const img = previewImageRef.value
    const wrap = previewWrapRef.value
    if (!img || !wrap) {
      return
    }
    previewImageNaturalWidth.value = img.naturalWidth
    previewImageNaturalHeight.value = img.naturalHeight
    const fitScale = Math.min(
      1,
      wrap.clientWidth / img.naturalWidth,
      wrap.clientHeight / img.naturalHeight,
    )
    previewBaseScale.value = Number(Math.max(0.5, fitScale).toFixed(2))
    resetPreviewTransform()
  }

  function togglePreviewZoom() {
    const fit = previewBaseScale.value
    const current = previewScale.value
    if (Math.abs(current - fit) < 0.05) {
      setPreviewScale(1)
      return
    }
    if (Math.abs(current - 1) < 0.05) {
      setPreviewScale(2)
      return
    }
    resetPreviewTransform()
  }

  return {
    canDragPreview,
    closeImagePreview,
    downloadPreviewImage,
    handlePreviewImageLoad,
    handlePreviewWheel,
    imagePreviewAlt,
    imagePreviewSrc,
    imagePreviewVisible,
    openImagePreviewSource,
    previewImageNaturalHeight,
    previewImageNaturalWidth,
    previewImageRef,
    previewImageSizeText,
    previewImageStyle,
    previewScale,
    previewWrapRef,
    resetPreviewTransform,
    startImageDrag,
    stopImageDrag,
    togglePreviewZoom,
    zoomInPreview,
    zoomOutPreview,
  }
}
