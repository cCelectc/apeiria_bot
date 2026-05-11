declare module 'markdown-it' {
  export interface MarkdownItToken {
    attrGet: (name: string) => string | null
    attrSet: (name: string, value: string) => void
  }

  export interface MarkdownItRenderer {
    renderToken: (
      tokens: MarkdownItToken[],
      idx: number,
      options: unknown,
    ) => string
  }

  export type MarkdownItRenderRule = (
    tokens: MarkdownItToken[],
    idx: number,
    options: unknown,
    env: unknown,
    self: MarkdownItRenderer,
  ) => string

  export interface MarkdownItInstance {
    renderer: {
      rules: Record<string, MarkdownItRenderRule | undefined>
    }
    use: <Args extends unknown[]>(
      plugin: (instance: MarkdownItInstance, ...args: Args) => void,
      ...args: Args
    ) => MarkdownItInstance
    render: (src: string) => string
  }

  export interface MarkdownItOptions {
    breaks?: boolean
    html?: boolean
    linkify?: boolean
  }

  export default class MarkdownIt implements MarkdownItInstance {
    constructor(options?: MarkdownItOptions)

    renderer: {
      rules: Record<string, MarkdownItRenderRule | undefined>
    }

    use: <Args extends unknown[]>(
      plugin: (instance: MarkdownItInstance, ...args: Args) => void,
      ...args: Args
    ) => MarkdownItInstance

    render: (src: string) => string
  }
}
