declare module 'markdown-it-task-lists' {
  import type { MarkdownItInstance } from 'markdown-it'

  export interface MarkdownItTaskListOptions {
    enabled?: boolean
    label?: boolean
    labelAfter?: boolean
  }

  export default function markdownItTaskLists(
    instance: MarkdownItInstance,
    options?: MarkdownItTaskListOptions,
  ): void
}
