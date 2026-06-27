import type { FieldNode } from "@/types";

export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (typeof a !== "object") return false;

  const aArr = Array.isArray(a);
  const bArr = Array.isArray(b);
  if (aArr !== bArr) return false;
  if (aArr && bArr) {
    const bl = b as unknown[];
    if (a.length !== bl.length) return false;
    return (a as unknown[]).every((v, i) => deepEqual(v, bl[i]));
  }

  const ao = a as Record<string, unknown>;
  const bo = b as Record<string, unknown>;
  const ak = Object.keys(ao);
  const bk = Object.keys(bo);
  if (ak.length !== bk.length) return false;
  return ak.every(
    (k) =>
      Object.prototype.hasOwnProperty.call(bo, k) && deepEqual(ao[k], bo[k]),
  );
}

export type DiffKind = "added" | "removed" | "changed";

export interface DiffEntry {
  path: string;
  label: string;
  kind: DiffKind;
  before: unknown;
  after: unknown;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function tail(path: string): string {
  const i = path.lastIndexOf(".");
  return i >= 0 ? path.slice(i + 1) : path;
}

function labelFor(path: string, topLabels: Record<string, string>): string {
  if (!path.includes(".") && topLabels[path]) return topLabels[path];
  return tail(path);
}

function walk(
  orig: Record<string, unknown>,
  curr: Record<string, unknown>,
  prefix: string,
  topLabels: Record<string, string>,
  out: DiffEntry[],
): void {
  const keys = new Set([...Object.keys(orig), ...Object.keys(curr)]);
  for (const key of keys) {
    const path = prefix ? `${prefix}.${key}` : key;
    const inO = Object.prototype.hasOwnProperty.call(orig, key);
    const inC = Object.prototype.hasOwnProperty.call(curr, key);
    const before = orig[key];
    const after = curr[key];
    const label = labelFor(path, topLabels);
    if (inO && !inC) {
      out.push({ path, label, kind: "removed", before, after: undefined });
    } else if (!inO && inC) {
      out.push({ path, label, kind: "added", before: undefined, after });
    } else if (deepEqual(before, after)) {
      // unchanged
    } else if (isPlainObject(before) && isPlainObject(after)) {
      walk(before, after, path, topLabels, out);
    } else {
      out.push({ path, label, kind: "changed", before, after });
    }
  }
}

export function flattenDiff(
  original: Record<string, unknown>,
  current: Record<string, unknown>,
  fields: FieldNode[],
): DiffEntry[] {
  const topLabels: Record<string, string> = {};
  for (const f of fields) topLabels[f.key] = f.label;
  const out: DiffEntry[] = [];
  walk(original, current, "", topLabels, out);
  return out;
}

export type LineDiffKind = "same" | "add" | "del";

export interface LineDiffEntry {
  kind: LineDiffKind;
  text: string;
}

export function lineDiff(a: string, b: string): LineDiffEntry[] {
  const aLines = a.split("\n");
  const bLines = b.split("\n");
  const n = aLines.length;
  const m = bLines.length;

  const lcs: number[][] = Array.from({ length: n + 1 }, () =>
    new Array<number>(m + 1).fill(0),
  );
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] =
        aLines[i] === bLines[j]
          ? lcs[i + 1][j + 1] + 1
          : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }

  const out: LineDiffEntry[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (aLines[i] === bLines[j]) {
      out.push({ kind: "same", text: aLines[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      out.push({ kind: "del", text: aLines[i] });
      i++;
    } else {
      out.push({ kind: "add", text: bLines[j] });
      j++;
    }
  }
  while (i < n) {
    out.push({ kind: "del", text: aLines[i] });
    i++;
  }
  while (j < m) {
    out.push({ kind: "add", text: bLines[j] });
    j++;
  }
  return out;
}
