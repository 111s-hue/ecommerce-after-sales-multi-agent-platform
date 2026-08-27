import type { Role, ViewKey } from '../types'

const roleViews: Record<Role, readonly ViewKey[]> = {
  admin: ['overview', 'workbench', 'approvals', 'operations', 'conversations', 'knowledge', 'audit', 'insights'],
  approver: ['overview', 'workbench', 'approvals', 'operations', 'conversations', 'knowledge', 'audit'],
  customer: ['workbench', 'operations', 'conversations'],
}

const defaultViews: Record<Role, ViewKey> = {
  admin: 'overview',
  approver: 'overview',
  customer: 'workbench',
}

export function normalizeRole(value: unknown): Role {
  return value === 'admin' || value === 'approver' || value === 'customer' ? value : 'customer'
}

export function canAccessView(role: Role, view: ViewKey): boolean {
  return roleViews[role].includes(view)
}

export function visibleViews(role: Role): readonly ViewKey[] {
  return roleViews[role]
}

export function defaultViewForRole(role: Role): ViewKey {
  return defaultViews[role]
}

export function canApprove(role: Role): boolean {
  return role === 'admin' || role === 'approver'
}

export function canPublishKnowledge(role: Role): boolean {
  return role === 'admin'
}
