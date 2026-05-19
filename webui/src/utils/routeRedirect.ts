export const DEFAULT_AUTH_REDIRECT = '/dashboard'

export function normalizeAuthRedirect(value: unknown, origin = currentOrigin()): string {
  const candidate = firstString(value).trim()
  if (!candidate || !candidate.startsWith('/')) {
    return DEFAULT_AUTH_REDIRECT
  }
  if (candidate.startsWith('//')) {
    return DEFAULT_AUTH_REDIRECT
  }
  try {
    const parsed = new URL(candidate, origin)
    if (parsed.origin !== origin) {
      return DEFAULT_AUTH_REDIRECT
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}` || DEFAULT_AUTH_REDIRECT
  } catch {
    return DEFAULT_AUTH_REDIRECT
  }
}

export function buildAuthRedirect(fullPath: string): string {
  return normalizeAuthRedirect(fullPath)
}

function currentOrigin() {
  return typeof window === 'undefined'
    ? 'http://localhost'
    : window.location.origin
}

function firstString(value: unknown) {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    return value.find(item => typeof item === 'string') ?? ''
  }
  return ''
}
