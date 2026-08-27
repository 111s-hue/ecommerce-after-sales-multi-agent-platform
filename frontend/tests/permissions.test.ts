import assert from 'node:assert/strict'
import test from 'node:test'

import {
  canAccessView,
  canApprove,
  canPublishKnowledge,
  defaultViewForRole,
  visibleViews,
} from '../src/security/permissions.ts'

test('admin can access every console module', () => {
  assert.equal(visibleViews('admin').length, 8)
  assert.equal(canPublishKnowledge('admin'), true)
  assert.equal(canApprove('admin'), true)
})

test('approver has governance access without admin-only publishing and evaluation', () => {
  assert.equal(canAccessView('approver', 'approvals'), true)
  assert.equal(canAccessView('approver', 'knowledge'), true)
  assert.equal(canAccessView('approver', 'insights'), false)
  assert.equal(canPublishKnowledge('approver'), false)
})

test('customer only sees their service workspace', () => {
  assert.deepEqual(visibleViews('customer'), ['workbench', 'operations', 'conversations'])
  assert.equal(defaultViewForRole('customer'), 'workbench')
  assert.equal(canApprove('customer'), false)
  assert.equal(canAccessView('customer', 'audit'), false)
})
