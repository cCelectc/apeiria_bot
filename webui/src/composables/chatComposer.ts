import type { ChatSegment } from '@/types/chat'

export interface PendingImage {
  id: string
  name: string
  size: number
  mime: string
  base64: string
  previewUrl: string
}

export interface PendingMention {
  id: string
  target: string
  display: string
}

export function getOrderedComposerImages(
  composer: HTMLElement | null | undefined,
  composerImages: Map<string, PendingImage>,
) {
  if (!composer) {
    return [] as PendingImage[]
  }
  const ids = Array.from(
    composer.querySelectorAll<HTMLElement>(
      '[data-kind="image-token"][data-image-id]',
    ),
  )
    .map(node => node.dataset.imageId || '')
    .filter(Boolean)

  return ids.flatMap(id => {
    const image = composerImages.get(id)
    return image ? [image] : []
  })
}

export async function readPendingImageFile(
  file: File,
  readFailedMessage: string,
): Promise<PendingImage> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.addEventListener('load', () => resolve(String(reader.result || '')))
    reader.addEventListener(
      'error',
      () => reject(reader.error || new Error(readFailedMessage)),
    )
    reader.readAsDataURL(file)
  })

  const [prefix, base64 = ''] = dataUrl.split(',', 2)
  const mimeMatch = prefix.match(/^data:(.+);base64$/)

  return {
    base64,
    id: `${file.name}_${file.lastModified}_${Math.random().toString(16).slice(2)}`,
    mime: mimeMatch?.[1] || file.type || 'image/png',
    name: file.name,
    previewUrl: dataUrl,
    size: file.size,
  }
}

export function createComposerImageNode(image: PendingImage, labelText: string) {
  const wrapper = document.createElement('span')
  wrapper.className = 'composer-image-token'
  wrapper.contentEditable = 'false'
  wrapper.dataset.imageId = image.id
  wrapper.dataset.kind = 'image-token'

  const label = document.createElement('span')
  label.className = 'composer-image-token__label'
  label.dataset.role = 'token-label'
  label.textContent = labelText

  const remove = document.createElement('button')
  remove.type = 'button'
  remove.className = 'composer-image-token__remove'
  remove.dataset.action = 'remove-image'
  remove.dataset.imageId = image.id
  remove.textContent = 'x'

  wrapper.append(label, remove)
  return wrapper
}

export function getComposerImageToken(
  composer: HTMLElement | null | undefined,
  id: string,
) {
  return composer?.querySelector<HTMLElement>(
    `[data-kind="image-token"][data-image-id="${id}"]`,
  ) || null
}

export function syncComposerImageTokenState(
  composer: HTMLElement | null | undefined,
  selectedComposerImageId: string | null,
) {
  if (!composer) {
    return
  }
  const tokens = Array.from(
    composer.querySelectorAll<HTMLElement>(
      '[data-kind="image-token"][data-image-id]',
    ),
  )
  for (const token of tokens) {
    token.classList.toggle(
      'composer-image-token--selected',
      token.dataset.imageId === selectedComposerImageId,
    )
  }
}

export function syncComposerImageTokenLabels(
  composer: HTMLElement | null | undefined,
  getLabel: (index: number) => string,
) {
  if (!composer) {
    return
  }
  const tokens = Array.from(
    composer.querySelectorAll<HTMLElement>(
      '[data-kind="image-token"][data-image-id]',
    ),
  )
  for (const [index, token] of tokens.entries()) {
    const label = token.querySelector<HTMLElement>('[data-role="token-label"]')
    if (label) {
      label.textContent = getLabel(index)
    }
  }
}

export function buildComposerSegmentsFromRoot(
  composer: HTMLElement | null | undefined,
  composerImages: Map<string, PendingImage>,
  composerMentions: Map<string, PendingMention>,
) {
  if (!composer) {
    return [] as ChatSegment[]
  }

  const segments: ChatSegment[] = []
  let textBuffer = ''

  const flushText = () => {
    if (textBuffer) {
      segments.push({ type: 'text', text: textBuffer })
      textBuffer = ''
    }
  }

  const walkNode = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      textBuffer += node.textContent || ''
      return
    }
    if (!(node instanceof HTMLElement)) {
      return
    }

    if (node.dataset.kind === 'image-token' && node.dataset.imageId) {
      const image = composerImages.get(node.dataset.imageId)
      if (image) {
        flushText()
        segments.push({
          alt: image.name,
          base64: image.base64,
          mime: image.mime,
          type: 'image',
        })
      }
      return
    }

    if (node.dataset.kind === 'mention-token' && node.dataset.mentionId) {
      const mention = composerMentions.get(node.dataset.mentionId)
      if (mention) {
        flushText()
        segments.push({
          display: mention.display,
          mention_type: 'user',
          target: mention.target,
          type: 'mention',
        })
      }
      return
    }

    if (node.tagName === 'BR') {
      textBuffer += '\n'
      return
    }

    const isBlock = ['DIV', 'P'].includes(node.tagName)
    if (isBlock && textBuffer && !textBuffer.endsWith('\n')) {
      textBuffer += '\n'
    }
    for (const childNode of node.childNodes) {
      walkNode(childNode)
    }
    if (isBlock && textBuffer && !textBuffer.endsWith('\n')) {
      textBuffer += '\n'
    }
  }

  for (const childNode of composer.childNodes) {
    walkNode(childNode)
  }
  flushText()

  return segments
    .map(segment => {
      if (segment.type !== 'text') {
        return segment
      }
      return { ...segment, text: segment.text.replace(/\u00A0/g, ' ') }
    })
    .filter(segment => segment.type !== 'text' || segment.text.length > 0)
}
