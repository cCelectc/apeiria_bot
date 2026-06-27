import { describe, expect, it } from 'vitest'
import type { FieldNode } from '@/types'
import { deepEqual, flattenDiff, lineDiff } from '../configDiff'

describe('deepEqual', () => {
  it('ignores object key order', () => {
    expect(deepEqual({ a: 1, b: 2 }, { b: 2, a: 1 })).toBe(true)
  })
  it('compares arrays by order', () => {
    expect(deepEqual([1, 2], [1, 2])).toBe(true)
    expect(deepEqual([1, 2], [2, 1])).toBe(false)
  })
  it('is strict about scalar types', () => {
    expect(deepEqual(1, '1')).toBe(false)
    expect(deepEqual(1, 1)).toBe(true)
  })
  it('recurses nested structures', () => {
    expect(deepEqual({ o: { x: 1 } }, { o: { x: 1 } })).toBe(true)
    expect(deepEqual({ o: { x: 1 } }, { o: { x: 2 } })).toBe(false)
  })
})

const portField = {
  kind: 'primitive',
  key: 'a',
  label: '端口',
  description: '',
  type: 'int',
  default: 8080,
  required: false,
  secret: false,
  order: 0,
} as unknown as FieldNode

describe('flattenDiff', () => {
  it('reports changed with label from fields', () => {
    expect(flattenDiff({ a: 1 }, { a: 2 }, [portField])).toEqual([
      { path: 'a', label: '端口', kind: 'changed', before: 1, after: 2 },
    ])
  })
  it('reports added and removed, label falls back to path tail', () => {
    expect(flattenDiff({ a: 1 }, { a: 1, b: 3 }, [])).toEqual([
      { path: 'b', label: 'b', kind: 'added', before: undefined, after: 3 },
    ])
    expect(flattenDiff({ a: 1, c: 9 }, { a: 1 }, [])).toEqual([
      { path: 'c', label: 'c', kind: 'removed', before: 9, after: undefined },
    ])
  })
  it('returns empty when equal', () => {
    expect(flattenDiff({ a: 1 }, { a: 1 }, [])).toEqual([])
  })
  it('recurses into nested objects with dotted path', () => {
    expect(flattenDiff({ o: { x: 1 } }, { o: { x: 2 } }, [])).toEqual([
      { path: 'o.x', label: 'x', kind: 'changed', before: 1, after: 2 },
    ])
  })
})

describe('lineDiff', () => {
  it('marks same/del/add lines', () => {
    expect(lineDiff('x\ny', 'x\nz')).toEqual([
      { kind: 'same', text: 'x' },
      { kind: 'del', text: 'y' },
      { kind: 'add', text: 'z' },
    ])
  })
  it('keeps identical lines as same', () => {
    expect(lineDiff('a\nb', 'a\nb')).toEqual([
      { kind: 'same', text: 'a' },
      { kind: 'same', text: 'b' },
    ])
  })
  it('detects an added line', () => {
    expect(lineDiff('a', 'a\nb')).toEqual([
      { kind: 'same', text: 'a' },
      { kind: 'add', text: 'b' },
    ])
  })
})
