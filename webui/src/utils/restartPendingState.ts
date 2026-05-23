export interface RestartPendingRuntimeEntry {
  updated_at: string
}

export function runtimeStartedAtFromUptime(
  uptimeSeconds: number | null | undefined,
  observedAt: Date = new Date(),
) {
  if (
    typeof uptimeSeconds !== 'number'
    || !Number.isFinite(uptimeSeconds)
    || uptimeSeconds < 0
  ) {
    return null
  }

  const observedTime = observedAt.getTime()
  if (!Number.isFinite(observedTime)) {
    return null
  }

  return new Date(observedTime - uptimeSeconds * 1000)
}

export function filterPendingEntriesForRuntime<
  Entry extends RestartPendingRuntimeEntry,
>(entries: Entry[], runtimeStartedAt: Date | null) {
  if (!runtimeStartedAt) {
    return entries
  }

  const runtimeStartedAtMs = runtimeStartedAt.getTime()
  if (!Number.isFinite(runtimeStartedAtMs)) {
    return entries
  }

  return entries.filter(entry => {
    const updatedAtMs = Date.parse(entry.updated_at)
    return !Number.isFinite(updatedAtMs) || updatedAtMs > runtimeStartedAtMs
  })
}
