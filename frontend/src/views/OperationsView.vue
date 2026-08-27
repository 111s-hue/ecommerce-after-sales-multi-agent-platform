<script setup lang="ts">
import { Box, Plus, Tickets } from '@element-plus/icons-vue'
import { computed, reactive, ref } from 'vue'
import type { AfterSale, Order, Role } from '../types'

interface CreateCasePayload {
  order_id: string
  customer_id: string
  case_type: string
  reason: string
  requested_amount?: number
  priority: string
}

const props = defineProps<{
  orders: Order[]
  afterSales: AfterSale[]
  userId: string
  role: Role
  permissions: string[]
  loading: boolean
  activeTab: 'orders' | 'tickets'
}>()
const emit = defineEmits<{
  'update:activeTab': [tab: 'orders' | 'tickets']
  'create-case': [payload: CreateCasePayload]
  'review-case': [payload: { caseId: string; approved: boolean }]
  'execute-refund': [payload: { caseId: string; refundId: string }]
  'complete-case': [caseId: string]
}>()

const active = computed({
  get: () => props.activeTab,
  set: (value: 'orders' | 'tickets') => emit('update:activeTab', value),
})
const showCreate = ref(false)
const form = reactive({
  order_id: 'ORD-1001',
  customer_id: props.userId,
  case_type: 'refund_only',
  reason: '',
  requested_amount: 0,
})
const canReview = computed(() => props.permissions.includes('approval.decide'))
const canExecuteRefund = computed(() => props.permissions.includes('refund.execute'))
const orderLabels: Record<string, string> = {
  paid: '待发货', shipped: '运输中', delivered: '已签收', closed: '已关闭',
}
const caseTypeLabels: Record<string, string> = {
  refund_only: '仅退款', return_refund: '退货退款', exchange: '换货',
  reshipment: '补发', repair: '维修', compensation: '补偿', appeal: '申诉',
}
const statusLabels: Record<string, string> = {
  submitted: '待审核', under_review: '审核中', pending_approval: '待审批',
  approved: '已批准', awaiting_customer_return: '待客户寄回',
  awaiting_receipt: '待收货验收', processing: '履约中', completed: '已完成',
  rejected: '已拒绝', cancelled: '已取消', pending: '待执行', succeeded: '已成功',
}
const amountRequired = computed(() =>
  ['refund_only', 'return_refund', 'compensation'].includes(form.case_type),
)

function submitCase() {
  if (!form.order_id.trim() || !form.reason.trim()) return
  const payload: CreateCasePayload = {
    order_id: form.order_id.trim(),
    customer_id: props.role === 'customer' ? props.userId : form.customer_id.trim(),
    case_type: form.case_type,
    reason: form.reason.trim(),
    priority: 'normal',
  }
  if (amountRequired.value) payload.requested_amount = Number(form.requested_amount)
  emit('create-case', payload)
  showCreate.value = false
  form.reason = ''
}
</script>

<template>
  <div class="view-stack">
    <section class="ledger-switch">
      <button :class="{ active: active === 'orders' }" type="button" @click="active = 'orders'">
        <el-icon><Box /></el-icon><span>订单台账<small>消费者订单与履约状态</small></span><b>{{ orders.length }}</b>
      </button>
      <button :class="{ active: active === 'tickets' }" type="button" @click="active = 'tickets'">
        <el-icon><Tickets /></el-icon><span>售后工单<small>全类型售后与履约状态</small></span><b>{{ afterSales.length }}</b>
      </button>
    </section>

    <section v-if="showCreate" class="panel case-create-panel">
      <header class="panel-header">
        <div><span class="section-kicker">SERVICE REQUEST</span><h3>创建售后申请</h3></div>
        <button class="text-action" type="button" @click="showCreate = false">收起</button>
      </header>
      <form class="case-form" @submit.prevent="submitCase">
        <label><span>订单号</span><input v-model="form.order_id" maxlength="32" required /></label>
        <label v-if="role !== 'customer'"><span>客户账号</span><input v-model="form.customer_id" maxlength="36" required /></label>
        <label><span>售后类型</span><select v-model="form.case_type">
          <option v-for="(label, key) in caseTypeLabels" :key="key" :value="key">{{ label }}</option>
        </select></label>
        <label v-if="amountRequired"><span>申请金额</span><input v-model.number="form.requested_amount" type="number" min="0.01" step="0.01" required /></label>
        <label class="form-wide"><span>申请原因</span><textarea v-model="form.reason" maxlength="2000" required placeholder="请说明问题、期望处理方式和必要凭证信息"></textarea></label>
        <div class="form-actions form-wide"><el-button @click="showCreate = false">取消</el-button><el-button type="primary" native-type="submit" :loading="loading">提交申请</el-button></div>
      </form>
    </section>

    <section class="panel table-panel">
      <header class="panel-header">
        <div><span class="section-kicker">BUSINESS LEDGER</span><h3>{{ active === 'orders' ? '订单台账' : '售后工单' }}</h3></div>
        <div class="panel-actions"><span class="table-count">{{ active === 'orders' ? orders.length : afterSales.length }} 条记录</span><el-button v-if="active === 'tickets'" type="primary" @click="showCreate = !showCreate"><el-icon><Plus /></el-icon>创建售后</el-button></div>
      </header>
      <el-table v-if="active === 'orders'" :data="orders" class="enterprise-table" empty-text="暂无订单">
        <el-table-column label="订单 / 商品" min-width="220"><template #default="scope"><div class="cell-primary"><strong>{{ scope.row.order_id }}</strong><small>{{ scope.row.product_name }}</small></div></template></el-table-column>
        <el-table-column prop="user_id" label="用户" width="110" />
        <el-table-column label="订单金额" min-width="120"><template #default="scope"><strong class="money">¥{{ Number(scope.row.amount).toFixed(2) }}</strong></template></el-table-column>
        <el-table-column label="履约状态" min-width="130"><template #default="scope"><span :class="['status-pill', scope.row.status]"><i></i>{{ orderLabels[scope.row.status] || scope.row.status }}</span></template></el-table-column>
        <el-table-column label="创建时间" min-width="180"><template #default="scope">{{ new Date(scope.row.created_at).toLocaleString('zh-CN') }}</template></el-table-column>
      </el-table>
      <el-table v-else :data="afterSales" class="enterprise-table" empty-text="暂无售后工单">
        <el-table-column label="售后单 / 订单" min-width="210"><template #default="scope"><div class="cell-primary"><strong>{{ scope.row.case_no }}</strong><small>{{ scope.row.order_id }}</small></div></template></el-table-column>
        <el-table-column prop="customer_id" label="客户" width="110" />
        <el-table-column label="类型" width="110"><template #default="scope">{{ caseTypeLabels[scope.row.case_type] || scope.row.case_type }}</template></el-table-column>
        <el-table-column prop="reason" label="申请原因" min-width="190" show-overflow-tooltip />
        <el-table-column label="申请 / 批准金额" min-width="150"><template #default="scope"><strong v-if="scope.row.requested_amount" class="money">¥{{ scope.row.approved_amount || scope.row.requested_amount }}</strong><span v-else>—</span></template></el-table-column>
        <el-table-column label="状态" min-width="130"><template #default="scope"><span :class="['status-pill', scope.row.status]"><i></i>{{ statusLabels[scope.row.status] || scope.row.status }}</span></template></el-table-column>
        <el-table-column label="业务操作" min-width="220" fixed="right"><template #default="scope"><div class="row-actions">
          <template v-if="canReview && ['submitted', 'under_review', 'pending_approval'].includes(scope.row.status)"><button type="button" @click="emit('review-case', { caseId: scope.row.case_id, approved: true })">批准</button><button class="danger" type="button" @click="emit('review-case', { caseId: scope.row.case_id, approved: false })">拒绝</button></template>
          <button v-if="canExecuteRefund && scope.row.refunds?.[0]?.status === 'pending'" type="button" @click="emit('execute-refund', { caseId: scope.row.case_id, refundId: scope.row.refunds[0].refund_id })">执行退款</button>
          <button v-if="canReview && scope.row.status === 'processing' && !scope.row.refunds?.length" type="button" @click="emit('complete-case', scope.row.case_id)">完成履约</button>
          <span v-if="scope.row.status === 'awaiting_customer_return'" class="action-hint">等待寄回</span>
        </div></template></el-table-column>
      </el-table>
    </section>
  </div>
</template>
