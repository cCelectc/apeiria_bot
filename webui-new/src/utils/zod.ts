import type { ZodError } from "zod"

export function flattenZodErrors(error: ZodError): Record<string, string> {
  const result: Record<string, string> = {}
  for (const issue of error.issues) {
    const path = issue.path.join(".")
    const key = path || "root"
    if (!result[key]) {
      result[key] = issue.message
    }
  }
  return result
}
