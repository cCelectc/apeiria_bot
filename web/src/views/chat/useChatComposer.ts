import type { ChatSegment } from '@/types/chat'
import { computed, ref } from 'vue'
import {
  buildComposerSegmentsFromRoot,
  createComposerImageNode,
  getComposerImageToken as findComposerImageToken,
  getOrderedComposerImages,
  type PendingImage,
  type PendingMention,
  readPendingImageFile,
  syncComposerImageTokenLabels as syncComposerImageLabels,
  syncComposerImageTokenState as syncComposerImageState,
} from '@/views/chat/composer'
import { formatBytes } from '@/views/chat/mediaPreview'

export function useChatComposer (options: {
  canSend: () => boolean
  imageIndexedToken: (index: number) => string
  imageReadFailed: () => string
  imageToken: () => string
  onSend: () => void
  openImagePreviewSource: (src: string, alt: string, sizeText: string) => void
}) {
  let composerRange: Range | null = null
  const composerRef = ref<HTMLDivElement>()
  const imageInputRef = ref<HTMLInputElement>()
  const isPreparingImages = ref(false)
  const composerVersion = ref(0)
  const selectedComposerImageId = ref<string | null>(null)
  const composerImages = new Map<string, PendingImage>()
  const composerMentions = new Map<string, PendingMention>()

  const composerHasContent = computed(() => {
    const segments = buildComposerSegments()
    return segments.some(segment => {
      if (segment.type === 'text') {
        return segment.text.trim().length > 0
      }
      return true
    })
  })

  const orderedComposerImages = computed(() => {
    void composerVersion.value
    return getOrderedComposerImages(composerRef.value, composerImages)
  })

  function pickImages () {
    imageInputRef.value?.click()
  }

  async function handleImageSelection (event: Event) {
    const target = event.target as HTMLInputElement | null
    const files = Array.from(target?.files || [])
    if (files.length === 0) {
      return
    }

    isPreparingImages.value = true
    try {
      const images = await Promise.all(
        files.map(file => readPendingImageFile(file, options.imageReadFailed())),
      )
      for (const image of images) {
        composerImages.set(image.id, image)
        insertImageIntoComposer(image)
      }
    } finally {
      isPreparingImages.value = false
      if (target) {
        target.value = ''
      }
    }
  }

  function touchComposer () {
    composerVersion.value += 1
  }

  function captureComposerSelection () {
    const composer = composerRef.value
    if (!composer) {
      return
    }
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) {
      return
    }
    const range = selection.getRangeAt(0)
    if (!composer.contains(range.commonAncestorContainer)) {
      return
    }
    composerRange = range.cloneRange()
  }

  function focusComposer (placeAtEnd = false) {
    const composer = composerRef.value
    if (!composer) {
      return
    }
    composer.focus()
    const selection = window.getSelection()
    if (!selection) {
      return
    }

    let range = composerRange
    if (placeAtEnd || !range || !composer.contains(range.commonAncestorContainer)) {
      range = document.createRange()
      range.selectNodeContents(composer)
      range.collapse(false)
    }

    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
  }

  function insertTextAtCursor (text: string) {
    focusComposer()
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) {
      return
    }
    const range = selection.getRangeAt(0)
    range.deleteContents()
    const node = document.createTextNode(text)
    range.insertNode(node)
    range.setStartAfter(node)
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
    touchComposer()
  }

  function getComposerImageToken (id: string) {
    return findComposerImageToken(composerRef.value, id)
  }

  function syncComposerImageTokenState () {
    syncComposerImageState(composerRef.value, selectedComposerImageId.value)
  }

  function selectComposerImage (id: string | null) {
    selectedComposerImageId.value = id
    syncComposerImageTokenState()
  }

  function insertImageIntoComposer (image: PendingImage) {
    focusComposer()
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) {
      return
    }
    const range = selection.getRangeAt(0)
    range.deleteContents()

    const token = createComposerImageNode(image, options.imageToken())
    const caretAnchor = document.createTextNode('')
    range.insertNode(caretAnchor)
    range.insertNode(token)

    range.setStart(caretAnchor, 0)
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
    syncComposerImageTokenLabels()
    selectComposerImage(image.id)
    touchComposer()
  }

  function removeComposerImage (id: string) {
    const composer = composerRef.value
    if (!composer) {
      return
    }
    const node = composer.querySelector<HTMLElement>(`[data-image-id="${id}"]`)
    node?.remove()
    composerImages.delete(id)
    if (selectedComposerImageId.value === id) {
      selectComposerImage(null)
    }
    focusComposer(true)
    syncComposerImageTokenLabels()
    touchComposer()
  }

  function removeComposerMention (id: string) {
    const composer = composerRef.value
    if (!composer) {
      return
    }
    const node = composer.querySelector<HTMLElement>(`[data-kind="mention-token"][data-mention-id="${id}"]`)
    node?.remove()
    composerMentions.delete(id)
    focusComposer(true)
    touchComposer()
  }

  function placeCaretAroundToken (node: HTMLElement, direction: 'before' | 'after') {
    const selection = window.getSelection()
    if (!selection) {
      return
    }
    const range = document.createRange()
    if (direction === 'before') {
      range.setStartBefore(node)
    } else {
      range.setStartAfter(node)
    }
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
  }

  function moveComposerImageToCursor (id: string) {
    const token = getComposerImageToken(id)
    if (!token) {
      return
    }
    focusComposer()
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) {
      return
    }
    const range = selection.getRangeAt(0)
    if (token.contains(range.commonAncestorContainer)) {
      return
    }
    token.remove()
    range.deleteContents()
    const caretAnchor = document.createTextNode('')
    range.insertNode(caretAnchor)
    range.insertNode(token)
    range.setStart(caretAnchor, 0)
    range.collapse(true)
    selection.removeAllRanges()
    selection.addRange(range)
    composerRange = range.cloneRange()
    syncComposerImageTokenLabels()
    selectComposerImage(id)
    touchComposer()
  }

  function handleComposerInput () {
    syncComposerImageTokenLabels()
    syncComposerImageTokenState()
    touchComposer()
    captureComposerSelection()
  }

  function handleComposerKeydown (event: KeyboardEvent) {
    if (!options.canSend() && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      return
    }
    const selectedId = selectedComposerImageId.value
    if (selectedId) {
      const token = getComposerImageToken(selectedId)
      if (token) {
        if (event.key === 'Backspace' || event.key === 'Delete') {
          event.preventDefault()
          removeComposerImage(selectedId)
          return
        }
        if (event.key === 'ArrowLeft') {
          event.preventDefault()
          selectComposerImage(null)
          placeCaretAroundToken(token, 'before')
          return
        }
        if (event.key === 'ArrowRight') {
          event.preventDefault()
          selectComposerImage(null)
          placeCaretAroundToken(token, 'after')
          return
        }
      }
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      options.onSend()
    }
  }

  function handleComposerClick (event: MouseEvent) {
    const target = event.target as HTMLElement | null
    if (!target) {
      return
    }
    const removeButton = target.closest<HTMLElement>('[data-action="remove-image"]')
    if (removeButton?.dataset.imageId) {
      event.preventDefault()
      removeComposerImage(removeButton.dataset.imageId)
      return
    }
    const removeMentionButton = target.closest<HTMLElement>('[data-action="remove-mention"]')
    if (removeMentionButton?.dataset.mentionId) {
      event.preventDefault()
      removeComposerMention(removeMentionButton.dataset.mentionId)
      return
    }
    const imageToken = target.closest<HTMLElement>('[data-kind="image-token"][data-image-id]')
    if (imageToken?.dataset.imageId) {
      event.preventDefault()
      selectComposerImage(imageToken.dataset.imageId)
      return
    }
    const mentionToken = target.closest<HTMLElement>('[data-kind="mention-token"][data-mention-id]')
    if (mentionToken) {
      event.preventDefault()
      return
    }
    selectComposerImage(null)
    captureComposerSelection()
  }

  function handleComposerPaste (event: ClipboardEvent) {
    event.preventDefault()
    const text = event.clipboardData?.getData('text/plain') || ''
    if (text) {
      insertTextAtCursor(text)
    }
  }

  function syncComposerImageTokenLabels () {
    syncComposerImageLabels(
      composerRef.value,
      index => options.imageIndexedToken(index),
    )
  }

  function buildComposerSegments (): ChatSegment[] {
    void composerVersion.value
    return buildComposerSegmentsFromRoot(
      composerRef.value,
      composerImages,
      composerMentions,
    )
  }

  function clearComposer () {
    const composer = composerRef.value
    if (composer) {
      composer.innerHTML = ''
    }
    for (const image of composerImages.values()) {
      URL.revokeObjectURL(image.previewUrl)
    }
    composerImages.clear()
    composerMentions.clear()
    composerRange = null
    selectComposerImage(null)
    touchComposer()
  }

  function openImagePreviewFromPending (image: PendingImage) {
    options.openImagePreviewSource(
      image.previewUrl,
      image.name,
      formatBytes(image.size),
    )
  }

  return {
    buildComposerSegments,
    captureComposerSelection,
    clearComposer,
    composerHasContent,
    composerRef,
    focusComposer,
    handleComposerClick,
    handleComposerInput,
    handleComposerKeydown,
    handleComposerPaste,
    handleImageSelection,
    imageInputRef,
    isPreparingImages,
    moveComposerImageToCursor,
    openImagePreviewFromPending,
    orderedComposerImages,
    pickImages,
    removeComposerImage,
    selectComposerImage,
    selectedComposerImageId,
  }
}
