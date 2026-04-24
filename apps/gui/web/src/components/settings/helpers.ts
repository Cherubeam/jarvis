// Shared helpers for the Settings view — path ops, schema lookups, error dispatch.

import type { JsonSchemaNode, SettingsValidationError } from '../../lib/types'

export type Path = Array<string | number>

export function getAt(obj: unknown, path: Path): unknown {
  let cur: unknown = obj
  for (const seg of path) {
    if (cur == null) return undefined
    if (typeof seg === 'number') {
      if (!Array.isArray(cur)) return undefined
      cur = cur[seg]
    } else {
      if (typeof cur !== 'object') return undefined
      cur = (cur as Record<string, unknown>)[seg]
    }
  }
  return cur
}

export function setAt<T>(obj: T, path: Path, value: unknown): T {
  if (path.length === 0) return value as T
  const [head, ...rest] = path
  if (typeof head === 'number') {
    const arr = Array.isArray(obj) ? [...(obj as unknown[])] : []
    arr[head] = setAt(arr[head], rest, value)
    return arr as unknown as T
  }
  const src = (obj && typeof obj === 'object' ? obj : {}) as Record<string, unknown>
  return { ...src, [head]: setAt(src[head], rest, value) } as unknown as T
}

export function deleteAt<T>(obj: T, path: Path): T {
  if (path.length === 0) return obj
  if (path.length === 1) {
    const [head] = path
    if (typeof head === 'number' && Array.isArray(obj)) {
      const arr = [...(obj as unknown[])]
      arr.splice(head, 1)
      return arr as unknown as T
    }
    const src = { ...(obj as Record<string, unknown>) }
    delete src[head as string]
    return src as unknown as T
  }
  const [head, ...rest] = path
  if (typeof head === 'number' && Array.isArray(obj)) {
    const arr = [...(obj as unknown[])]
    arr[head] = deleteAt(arr[head], rest)
    return arr as unknown as T
  }
  const src = (obj && typeof obj === 'object' ? obj : {}) as Record<string, unknown>
  return { ...src, [head as string]: deleteAt(src[head as string], rest) } as unknown as T
}

export function pathsEqual(a: Path, b: Path): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
  return true
}

export function pathStartsWith(full: Path, prefix: Path): boolean {
  if (full.length < prefix.length) return false
  for (let i = 0; i < prefix.length; i++) if (full[i] !== prefix[i]) return false
  return true
}

export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a == null || b == null) return a === b
  if (typeof a !== typeof b) return false
  if (Array.isArray(a)) {
    if (!Array.isArray(b) || a.length !== b.length) return false
    return a.every((v, i) => deepEqual(v, b[i]))
  }
  if (typeof a === 'object') {
    const ao = a as Record<string, unknown>
    const bo = b as Record<string, unknown>
    const keys = Object.keys(ao)
    if (keys.length !== Object.keys(bo).length) return false
    return keys.every((k) => deepEqual(ao[k], bo[k]))
  }
  return false
}

// --- Error dispatch --------------------------------------------------------

export function fieldErrorAt(
  errors: SettingsValidationError[],
  path: Path,
): string | null {
  const hit = errors.find(
    (e) => e.kind === 'field' && pathsEqual(e.loc, path),
  )
  return hit ? hit.msg : null
}

export function cardErrorsAt(
  errors: SettingsValidationError[],
  cardPath: Path,
): SettingsValidationError[] {
  return errors.filter(
    (e) => e.kind === 'model_validator' && pathsEqual(e.card_loc, cardPath),
  )
}

export function sectionHasErrors(
  errors: SettingsValidationError[],
  section: string,
): boolean {
  return errors.some((e) => e.loc[0] === section || e.card_loc[0] === section)
}

// --- Schema walking --------------------------------------------------------

export function schemaAt(
  schema: JsonSchemaNode | null,
  path: Path,
): JsonSchemaNode | null {
  if (!schema) return null
  let cur: JsonSchemaNode = schema
  for (const seg of path) {
    if (typeof seg === 'number') {
      const items = cur['items']
      if (!items || typeof items !== 'object') return null
      cur = items as JsonSchemaNode
      continue
    }
    const props = cur['properties']
    if (props && typeof props === 'object' && seg in (props as Record<string, unknown>)) {
      cur = (props as Record<string, JsonSchemaNode>)[seg]
      continue
    }
    const additional = cur['additionalProperties']
    if (additional && typeof additional === 'object') {
      cur = additional as JsonSchemaNode
      continue
    }
    return null
  }
  return cur
}

export type FieldType = 'string' | 'int' | 'float' | 'bool' | 'enum' | 'list_string' | 'unknown'

export function fieldType(node: JsonSchemaNode | null): FieldType {
  if (!node) return 'unknown'
  if (Array.isArray(node['enum'])) return 'enum'
  const t = node['type']
  if (Array.isArray(t)) {
    // Pydantic renders `str | None` as ["string", "null"] etc.
    const nonNull = t.find((x) => x !== 'null')
    if (nonNull === 'string') return 'string'
    if (nonNull === 'integer') return 'int'
    if (nonNull === 'number') return 'float'
    if (nonNull === 'boolean') return 'bool'
  }
  if (t === 'string') return 'string'
  if (t === 'integer') return 'int'
  if (t === 'number') return 'float'
  if (t === 'boolean') return 'bool'
  if (t === 'array') {
    const items = node['items']
    if (items && typeof items === 'object' && (items as JsonSchemaNode)['type'] === 'string') {
      return 'list_string'
    }
  }
  // Handle pydantic's anyOf for Optional[X].
  const anyOf = node['anyOf']
  if (Array.isArray(anyOf)) {
    const nonNull = anyOf.find(
      (o): o is JsonSchemaNode => typeof o === 'object' && o !== null && (o as JsonSchemaNode)['type'] !== 'null',
    )
    if (nonNull) return fieldType(nonNull)
  }
  return 'unknown'
}

export function fieldDescription(node: JsonSchemaNode | null): string {
  if (!node) return ''
  const d = node['description']
  return typeof d === 'string' ? d : ''
}

export function enumChoices(node: JsonSchemaNode | null): string[] {
  if (!node || !Array.isArray(node['enum'])) return []
  return (node['enum'] as unknown[]).filter((x): x is string => typeof x === 'string')
}
