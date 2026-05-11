import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import markdownItTaskLists from 'markdown-it-task-lists'

const markdown = new MarkdownIt({
  breaks: false,
  html: true,
  linkify: true,
})

markdown.use(markdownItTaskLists, {
  enabled: false,
  label: true,
  labelAfter: true,
})

export function resolveReadmeRelativeUrl(
  rawUrl: string,
  moduleName: string | null | undefined,
) {
  const normalized = rawUrl.trim()
  if (!normalized || !moduleName) {
    return normalized
  }

  if (
    normalized.startsWith('#')
    || normalized.startsWith('/')
    || normalized.startsWith('//')
    || /^[a-z][a-z0-9+.-]*:/i.test(normalized)
  ) {
    return normalized
  }

  const hashIndex = normalized.indexOf('#')
  const hash = hashIndex === -1 ? '' : normalized.slice(hashIndex)
  const pathWithQuery = hashIndex === -1
    ? normalized
    : normalized.slice(0, hashIndex)
  const queryIndex = pathWithQuery.indexOf('?')
  const relativePath = queryIndex === -1
    ? pathWithQuery
    : pathWithQuery.slice(0, queryIndex)

  if (!relativePath) {
    return normalized
  }

  const basePath = `/api/plugins/${encodeURIComponent(moduleName)}/readme/asset`
  const params = new URLSearchParams({ path: relativePath })
  return `${basePath}?${params.toString()}${hash}`
}

export function renderReadmeHtml(
  content: string,
  moduleName: string | null | undefined,
) {
  const sanitized = DOMPurify.sanitize(markdown.render(content), {
    ADD_ATTR: ['align'],
    ADD_TAGS: ['details', 'summary'],
  })
  const document = new DOMParser().parseFromString(sanitized, 'text/html')

  for (const element of document.querySelectorAll<HTMLAnchorElement>('a[href]')) {
    const href = element.getAttribute('href')
    if (!href) {
      continue
    }
    element.setAttribute('href', resolveReadmeRelativeUrl(href, moduleName))
    element.setAttribute('target', '_blank')
    element.setAttribute('rel', 'noopener noreferrer')
  }

  for (const element of document.querySelectorAll<HTMLImageElement>('img[src]')) {
    const src = element.getAttribute('src')
    if (!src) {
      continue
    }
    element.setAttribute('src', resolveReadmeRelativeUrl(src, moduleName))
  }

  return document.body.innerHTML
}
