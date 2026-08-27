import axios from 'axios'
import { computed, onMounted, ref, watch } from 'vue'
import {
  canAccessView,
  canApprove,
  canPublishKnowledge,
  defaultViewForRole,
  normalizeRole,
} from '../security/permissions'
import { api, errorMessage, streamChat } from '../services/api'
import type {
  AfterSale,
  AgentKey,
  Approval,
  AuditLog,
  ChatResult,
  Conversation,
  Evaluation,
  GlobalSearchResult,
  KnowledgeDocument,
  KnowledgePreview,
  LiveNode,
  NotificationItem,
  Order,
  Summary,
  SystemInfo,
  ViewKey,
} from '../types'

const viewTitles: Record<ViewKey, { title: string; description: string }> = {
  overview: { title: '售后协同总览', description: '聚合工单、智能分派、自动诊断、升级协作与闭环分析' },
  workbench: { title: '智能体协同', description: '发起并观察完整的多智能体协作链路' },
  approvals: { title: '人工审批中心', description: '处理敏感退款操作与风险例外' },
  operations: { title: '工单中心', description: '统一查看订单与售后工单' },
  conversations: { title: '会话质检', description: '追踪用户问题、意图与处理状态' },
  knowledge: { title: '知识库', description: '维护可溯源的售后政策知识库' },
  audit: { title: '规则审计', description: '检查每一次工具调用与安全决策' },
  insights: { title: '数据分析', description: '持续衡量任务成功率与路由准确率' },
}

export function useConsole() {
  const token = ref(sessionStorage.getItem('after-sales-token') || '')
  const loginRole = ref(normalizeRole(sessionStorage.getItem('after-sales-role')))
  const loginPermissions = ref<string[]>(
    JSON.parse(sessionStorage.getItem('after-sales-permissions') || '[]'),
  )
  const activeView = ref<ViewKey>(defaultViewForRole(loginRole.value))
  const loginUser = ref(localStorage.getItem('after-sales-login-user') || '')
  const loginPassword = ref('')
  const userId = ref('U1001')
  const query = ref('查询 ORD-1002 的物流到哪了')
  const threadId = ref(`web-${Date.now()}`)
  const selectedAgent = ref<AgentKey>('auto')
  const reviewer = ref('客服主管')
  const approvalReason = ref('订单、用户身份与退款金额核验通过')
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref('')
  const notice = ref('')
  const result = ref<ChatResult | null>(null)
  const liveNodes = ref<LiveNode[]>([])
  const approvals = ref<Approval[]>([])
  const conversations = ref<Conversation[]>([])
  const orders = ref<Order[]>([])
  const afterSales = ref<AfterSale[]>([])
  const documents = ref<KnowledgeDocument[]>([])
  const knowledgePreview = ref<KnowledgePreview | null>(null)
  const audits = ref<AuditLog[]>([])
  const summary = ref<Summary>({})
  const evaluation = ref<Evaluation>({ status: 'not_run' })
  const systemInfo = ref<SystemInfo | null>(null)
  const unreadCount = ref(0)
  const notifications = ref<NotificationItem[]>([])
  const searchResults = ref<GlobalSearchResult[]>([])
  const searchLoading = ref(false)
  const operationTab = ref<'orders' | 'tickets'>('orders')
  const uploadFile = ref<File | null>(null)

  const pending = computed(() => result.value?.status === 'pending_approval')
  const pageMeta = computed(() => viewTitles[activeView.value])
  const pendingCount = computed(() => approvals.value.filter((item) => item.status === 'pending').length)
  const canApproveCurrent = computed(() => canApprove(loginRole.value))
  const canPublishKnowledgeCurrent = computed(() => canPublishKnowledge(loginRole.value))

  function clearSession() {
    token.value = ''
    loginRole.value = 'customer'
    activeView.value = defaultViewForRole(loginRole.value)
    loginPassword.value = ''
    loginPermissions.value = []
    sessionStorage.removeItem('after-sales-token')
    sessionStorage.removeItem('after-sales-role')
    sessionStorage.removeItem('after-sales-permissions')
  }

  function captureError(exc: unknown) {
    if (axios.isAxiosError(exc) && exc.response?.status === 401 && token.value) {
      clearSession()
      error.value = '登录状态已失效，请重新登录'
      return
    }
    error.value = errorMessage(exc)
  }

  async function signIn() {
    error.value = ''
    notice.value = ''
    loading.value = true
    try {
      const response = await api.post('/auth/login', {
        username: loginUser.value.trim(),
        password: loginPassword.value,
      })
      token.value = response.data.access_token
      loginRole.value = normalizeRole(response.data.role)
      loginPermissions.value = Array.isArray(response.data.permissions) ? response.data.permissions : []
      activeView.value = defaultViewForRole(loginRole.value)
      if (loginRole.value === 'customer') userId.value = response.data.user_id
      sessionStorage.setItem('after-sales-token', token.value)
      sessionStorage.setItem('after-sales-role', loginRole.value)
      sessionStorage.setItem('after-sales-permissions', JSON.stringify(loginPermissions.value))
      localStorage.setItem('after-sales-login-user', loginUser.value.trim())
      loginPassword.value = ''
      await refreshCurrentView()
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  function signOut() {
    clearSession()
    error.value = ''
    notice.value = ''
  }

  async function sendMessage() {
    if (!query.value.trim()) return
    loading.value = true
    error.value = ''
    notice.value = ''
    liveNodes.value = []
    result.value = null
    try {
      result.value = await streamChat(
        {
          user_id: userId.value,
          thread_id: threadId.value,
          query: query.value.trim(),
          target_agent: selectedAgent.value,
        },
        (node) => liveNodes.value.push(node),
      )
      const postRunLoads: Promise<unknown>[] = [loadConversations()]
      if (canApproveCurrent.value) postRunLoads.push(loadApprovals(), loadSummary())
      await Promise.all(postRunLoads)
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  async function decide(approved: boolean, targetThread = threadId.value) {
    loading.value = true
    error.value = ''
    notice.value = ''
    try {
      const response = await api.post(`/approvals/${targetThread}`, {
        approved,
        reviewer: reviewer.value,
        reason: approvalReason.value,
      })
      if (targetThread === threadId.value) result.value = response.data
      await Promise.all([loadApprovals(), loadSummary(), loadConversations(), loadAfterSales()])
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  async function loadSummary() {
    summary.value = (await api.get('/metrics/summary')).data
  }
  async function loadApprovals() {
    approvals.value = (await api.get('/approvals')).data
  }
  async function loadConversations() {
    conversations.value = (await api.get('/conversations')).data
  }
  async function loadOrders() {
    orders.value = (await api.get('/orders')).data
  }
  async function loadAfterSales() {
    const response = await api.get('/after-sale-cases')
    afterSales.value = response.data.items
  }

  async function createAfterSale(payload: {
    order_id: string
    customer_id: string
    case_type: string
    reason: string
    requested_amount?: number
  }) {
    loading.value = true
    error.value = ''
    try {
      await api.post('/after-sale-cases', payload, {
        headers: { 'Idempotency-Key': `web-case-${crypto.randomUUID?.() || Date.now()}` },
      })
      notice.value = '售后申请已创建并进入审核队列'
      await loadAfterSales()
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  async function reviewAfterSale(caseId: string, approved: boolean) {
    loading.value = true
    error.value = ''
    try {
      await api.post(`/after-sale-cases/${caseId}/review`, {
        approved,
        reason: approved ? '业务资料核验通过' : '申请不符合当前售后政策',
      })
      notice.value = approved ? '售后申请已批准并创建履约子单' : '售后申请已拒绝'
      await loadAfterSales()
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  async function executeRefund(caseId: string, refundId: string) {
    loading.value = true
    error.value = ''
    try {
      await api.post(`/after-sale-cases/${caseId}/refunds/${refundId}/execute`)
      notice.value = '退款网关已处理完成'
      await loadAfterSales()
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  async function completeAfterSale(caseId: string) {
    loading.value = true
    error.value = ''
    try {
      await api.post(`/after-sale-cases/${caseId}/complete`, { notes: '履约结果已确认' })
      notice.value = '售后履约已完成'
      await loadAfterSales()
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }
  async function loadDocuments() {
    documents.value = (await api.get('/knowledge/documents')).data
  }
  async function loadAudits() {
    audits.value = (await api.get('/audit?limit=200')).data
  }
  async function loadEvaluation() {
    evaluation.value = (await api.get('/metrics/evaluation')).data
  }
  async function loadSystemInfo() {
    systemInfo.value = (await api.get('/system/info')).data
  }
  async function loadNotifications() {
    const response = await api.get('/notifications?limit=30')
    unreadCount.value = response.data.unread
    notifications.value = response.data.items
  }

  async function markNotificationRead(notificationId: string) {
    try {
      await api.patch(`/notifications/${notificationId}/read`)
      await loadNotifications()
    } catch (exc) {
      captureError(exc)
    }
  }

  async function globalSearch(term: string) {
    const keyword = term.trim().toLocaleLowerCase('zh-CN')
    searchResults.value = []
    if (!keyword) return
    searchLoading.value = true
    error.value = ''
    try {
      const requests: Promise<unknown>[] = [loadOrders(), loadAfterSales(), loadConversations()]
      if (canAccessView(loginRole.value, 'knowledge')) requests.push(loadDocuments())
      await Promise.all(requests)

      const matches = (...values: unknown[]) => values.some((value) =>
        String(value ?? '').toLocaleLowerCase('zh-CN').includes(keyword))
      const results: GlobalSearchResult[] = []
      for (const item of orders.value) {
        if (matches(item.order_id, item.user_id, item.product_name, item.status)) results.push({
          id: `order-${item.order_id}`, kind: '订单', title: item.order_id,
          description: `${item.user_id} · ${item.product_name} · ¥${Number(item.amount).toFixed(2)}`,
          view: 'operations', operationTab: 'orders',
        })
      }
      for (const item of afterSales.value) {
        if (matches(item.case_no, item.order_id, item.customer_id, item.reason, item.case_type, item.status)) results.push({
          id: `case-${item.case_id}`, kind: '售后工单', title: item.case_no,
          description: `${item.order_id} · ${item.customer_id} · ${item.reason}`,
          view: 'operations', operationTab: 'tickets',
        })
      }
      for (const item of conversations.value) {
        if (matches(item.thread_id, item.user_id, item.title, item.intent, item.status)) results.push({
          id: `conversation-${item.thread_id}`, kind: '会话', title: item.title || item.thread_id,
          description: `${item.user_id} · ${item.intent || '待识别'} · ${item.status}`,
          view: 'conversations',
        })
      }
      for (const item of documents.value) {
        if (matches(item.name, item.storage)) results.push({
          id: `document-${item.name}`, kind: '知识文档', title: item.name,
          description: `已发布 · ${Math.max(1, Math.ceil(item.size / 1024))} KB`, view: 'knowledge',
        })
      }
      const agents = [
        ['订单校验智能体', '查询订单状态、金额与履约信息'],
        ['物流查询智能体', '查询物流轨迹与配送异常'],
        ['退款策略智能体', '核验退款政策并发起审批'],
        ['质检分析智能体', '分析会话质量与合规风险'],
      ]
      for (const [name, description] of agents) {
        if (matches(name, description)) results.push({
          id: `agent-${name}`, kind: '智能体', title: name, description,
          view: 'workbench', suggestedQuery: `请使用${name}处理当前售后问题`,
        })
      }
      searchResults.value = results.slice(0, 40)
    } catch (exc) {
      captureError(exc)
    } finally {
      searchLoading.value = false
    }
  }

  async function uploadDocument() {
    if (!uploadFile.value || !canPublishKnowledgeCurrent.value) return
    loading.value = true
    error.value = ''
    notice.value = ''
    const filename = uploadFile.value.name
    try {
      const body = new FormData()
      body.append('file', uploadFile.value)
      await api.post('/knowledge/documents', body)
      uploadFile.value = null
      await loadDocuments()
      notice.value = `“${filename}”已发布，知识索引已完成更新`
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  async function previewDocument(filename: string) {
    loading.value = true
    error.value = ''
    try {
      knowledgePreview.value = (
        await api.get(`/knowledge/documents/${encodeURIComponent(filename)}`)
      ).data
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  async function downloadDocument(filename: string) {
    error.value = ''
    try {
      const response = await api.get(
        `/knowledge/documents/${encodeURIComponent(filename)}/download`,
        { responseType: 'blob' },
      )
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      notice.value = `“${filename}”已下载`
    } catch (exc) {
      captureError(exc)
    }
  }

  async function deleteDocument(filename: string) {
    loading.value = true
    error.value = ''
    try {
      await api.delete(`/knowledge/documents/${encodeURIComponent(filename)}`)
      if (knowledgePreview.value?.name === filename) knowledgePreview.value = null
      await loadDocuments()
      notice.value = `“${filename}”已从运行知识库退役，历史版本仍保留`
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  async function rebuildKnowledge() {
    loading.value = true
    error.value = ''
    try {
      const response = await api.post('/knowledge/rebuild')
      await loadDocuments()
      notice.value = `知识索引重建完成，共生成 ${response.data.chunks} 个知识片段`
    } catch (exc) {
      captureError(exc)
    } finally {
      loading.value = false
    }
  }

  function newConversation() {
    threadId.value = `web-${Date.now()}`
    result.value = null
    liveNodes.value = []
    error.value = ''
  }

  function startSuggestedTask(suggestion: string) {
    newConversation()
    query.value = suggestion
    activeView.value = 'workbench'
    notice.value = '处理策略已带入协同任务，请核对后运行流程'
  }

  async function refreshCurrentView() {
    if (!token.value) return
    if (!canAccessView(loginRole.value, activeView.value)) {
      activeView.value = defaultViewForRole(loginRole.value)
      return
    }
    refreshing.value = true
    error.value = ''
    try {
      const loaders: Record<ViewKey, () => Promise<unknown>> = {
        overview: () => Promise.all([loadSummary(), loadApprovals(), loadConversations(), loadSystemInfo()]),
        workbench: () => Promise.resolve(),
        approvals: loadApprovals,
        operations: () => Promise.all([loadOrders(), loadAfterSales()]),
        conversations: loadConversations,
        knowledge: loadDocuments,
        audit: loadAudits,
        insights: () => Promise.all([loadSummary(), loadEvaluation(), loadSystemInfo()]),
      }
      await Promise.all([loaders[activeView.value](), loadNotifications()])
    } catch (exc) {
      captureError(exc)
    } finally {
      refreshing.value = false
    }
  }

  watch(activeView, () => {
    if (!canAccessView(loginRole.value, activeView.value)) {
      activeView.value = defaultViewForRole(loginRole.value)
      return
    }
    if (token.value) void refreshCurrentView()
  })
  onMounted(() => {
    if (token.value) void refreshCurrentView()
  })

  return {
    activeView, token, loginRole, loginPermissions, loginUser, loginPassword, userId, query, threadId,
    selectedAgent,
    reviewer, approvalReason, loading, refreshing, error, notice, result, liveNodes, approvals,
    conversations, orders, afterSales, documents, knowledgePreview, audits, summary, evaluation,
    systemInfo, unreadCount,
    notifications, searchResults, searchLoading, operationTab,
    uploadFile, pending, pendingCount, pageMeta, canApproveCurrent, canPublishKnowledgeCurrent,
    signIn, signOut, sendMessage, decide,
    uploadDocument, newConversation, refreshCurrentView, createAfterSale, reviewAfterSale,
    executeRefund, completeAfterSale, loadNotifications, markNotificationRead, globalSearch,
    startSuggestedTask, previewDocument, downloadDocument, deleteDocument, rebuildKnowledge,
  }
}
