export type RequestCrypto = Partial<Pick<Crypto, 'randomUUID' | 'getRandomValues'>>

let fallbackCounter = 0

function uuidFromBytes(bytes: Uint8Array): string {
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

/**
 * Generates a correlation ID in HTTPS, localhost and plain-HTTP intranet environments.
 * randomUUID is intentionally optional because browsers hide it outside secure contexts.
 */
export function createRequestId(
  prefix = 'web',
  source: RequestCrypto | null | undefined = globalThis.crypto,
): string {
  if (typeof source?.randomUUID === 'function') {
    return `${prefix}-${source.randomUUID()}`
  }

  if (typeof source?.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    source.getRandomValues(bytes)
    return `${prefix}-${uuidFromBytes(bytes)}`
  }

  fallbackCounter += 1
  const timestamp = Date.now().toString(36)
  const random = Math.random().toString(36).slice(2, 12)
  return `${prefix}-${timestamp}-${fallbackCounter.toString(36)}-${random}`
}
