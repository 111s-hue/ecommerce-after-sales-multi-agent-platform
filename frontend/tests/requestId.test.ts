import assert from 'node:assert/strict'
import test from 'node:test'

import { createRequestId, type RequestCrypto } from '../src/services/requestId.ts'

test('uses randomUUID when the browser exposes it', () => {
  const source = { randomUUID: () => '00000000-0000-4000-8000-000000000001' }
  assert.equal(createRequestId('web', source), 'web-00000000-0000-4000-8000-000000000001')
})

test('falls back to getRandomValues in an insecure browser context', () => {
  const source = {
    getRandomValues(array: Uint8Array) {
      array.forEach((_, index) => { array[index] = index })
      return array
    },
  } as RequestCrypto
  const value = createRequestId('web', source)
  assert.match(value, /^web-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
})

test('still produces distinct IDs when the Crypto API is unavailable', () => {
  const first = createRequestId('web', null)
  const second = createRequestId('web', null)
  assert.notEqual(first, second)
  assert.match(first, /^web-/)
})
