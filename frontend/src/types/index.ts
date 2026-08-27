export type ViewKey =
  | 'overview'
  | 'workbench'
  | 'approvals'
  | 'operations'
  | 'conversations'
  | 'knowledge'
  | 'audit'
  | 'insights'

export type Role = 'admin' | 'approver' | 'customer'
export type AgentKey = 'auto' | 'order' | 'logistics' | 'policy' | 'refund'

export interface TraceEvent {
  node: string
  message: string
  at: string
}

export interface Evidence {
  source: string
  section: string
  content: string
  score: number
}

export interface ChatResult {
  status: 'completed' | 'pending_approval'
  thread_id: string
  intent?: string
  response: string
  trace: TraceEvent[]
  evidence: Evidence[]
  evidence_level?: string
  interrupts: Record<string, unknown>[]
  tool_results: Record<string, unknown>
  error?: string
}

export interface LiveNode {
  node: string
  message: string
}

export interface Approval {
  thread_id: string
  user_id: string
  order_id: string
  action: string
  amount: number
  status: string
  reviewer?: string
  reason: string
  created_at: string
  decided_at?: string
}

export interface Conversation {
  thread_id: string
  user_id: string
  title: string
  status: string
  intent?: string
  created_at: string
  updated_at: string
}

export interface Order {
  order_id: string
  user_id: string
  product_name: string
  amount: number
  status: string
  created_at: string
  delivered_at?: string
}

export interface AfterSale {
  case_id: string
  case_no: string
  order_id: string
  customer_id: string
  case_type: string
  reason: string
  requested_amount?: string
  approved_amount?: string
  currency: string
  status: string
  priority: string
  created_at: string
  refunds: Array<{
    refund_id: string
    refund_no: string
    amount: string
    status: string
    provider: string
  }>
  returns: Array<{ return_id: string; return_no: string; status: string }>
}

export interface KnowledgeDocument {
  document_id?: string
  version_id?: string
  version_no?: number
  name: string
  title?: string
  size: number
  updated_at: string
  storage: string
  status?: string
  index_status?: string
}

export interface KnowledgePreview extends KnowledgeDocument {
  content: string
}

export interface AuditLog {
  id: number
  thread_id: string
  user_id: string
  action: string
  resource: string
  outcome: string
  detail: string
  created_at: string
}

export interface SystemInfo {
  name: string
  version: string
  environment: string
  llm: { enabled: boolean; model: string }
  rag: { backend: string; top_k: number }
  tool_transport: string
  auth_enabled: boolean
}

export type Summary = Record<string, number>
export type Evaluation = Record<string, unknown> & {
  status?: string
  message?: string
  task_success_rate?: number
  passed?: number
  total?: number
  intent_accuracy?: number
  details?: Record<string, unknown>[]
}

export interface NotificationItem {
  notification_id: string
  channel: string
  template_code: string
  subject?: string
  payload_json: string
  status: string
  read_at?: string
  created_at: string
}

export interface GlobalSearchResult {
  id: string
  kind: '订单' | '售后工单' | '会话' | '知识文档' | '智能体'
  title: string
  description: string
  view: ViewKey
  operationTab?: 'orders' | 'tickets'
  suggestedQuery?: string
}
