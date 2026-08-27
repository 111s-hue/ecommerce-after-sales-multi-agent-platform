<script setup lang="ts">
import {
  CircleCheck, Collection, Connection, Delete, Operation, Promotion, RefreshRight,
  Tickets, Warning,
} from '@element-plus/icons-vue'
import type { AgentKey, ChatResult, LiveNode } from '../types'

defineProps<{
  userId: string
  threadId: string
  selectedAgent: AgentKey
  query: string
  reviewer: string
  approvalReason: string
  loading: boolean
  result: ChatResult | null
  liveNodes: LiveNode[]
  pending: boolean
  canApprove: boolean
  canSwitchUser: boolean
}>()
const emit = defineEmits<{
  'update:userId': [value: string]
  'update:threadId': [value: string]
  'update:selectedAgent': [value: AgentKey]
  'update:query': [value: string]
  'update:reviewer': [value: string]
  'update:approvalReason': [value: string]
  send: []
  decide: [approved: boolean]
  reset: []
}>()

const quickPrompts = ['查询 ORD-1001 的订单状态', 'ORD-1001 想退款', '七天无理由退货有什么条件？']
const agents = [
  { key: 'auto', name: '自动编排', detail: 'Supervisor 智能路由', icon: Operation },
  { key: 'order', name: '订单智能体', detail: '订单与履约校验', icon: Tickets },
  { key: 'logistics', name: '物流智能体', detail: '轨迹与异常查询', icon: Connection },
  { key: 'policy', name: '政策智能体', detail: '规则与知识检索', icon: Collection },
  { key: 'refund', name: '退款智能体', detail: '资格核验与审批', icon: CircleCheck },
] as const
</script>

<template>
  <div class="workbench-grid">
    <section class="panel command-panel">
      <header class="panel-header command-head">
        <div><span class="section-kicker">AGENT COMMAND</span><h3>协同任务</h3></div>
        <button class="quiet-button" type="button" @click="emit('reset')"><el-icon><RefreshRight /></el-icon> 新会话</button>
      </header>
      <div class="agent-selector">
        <div class="agent-selector-head"><span>执行智能体</span><small>指定专业智能体时仍会经过 Supervisor 安全校验</small></div>
        <div class="agent-options" role="radiogroup" aria-label="选择执行智能体">
          <button
            v-for="agent in agents"
            :key="agent.key"
            type="button"
            role="radio"
            :aria-checked="selectedAgent === agent.key"
            :class="{ active: selectedAgent === agent.key }"
            @click="emit('update:selectedAgent', agent.key)"
          >
            <span><el-icon><component :is="agent.icon" /></el-icon></span>
            <p><b>{{ agent.name }}</b><small>{{ agent.detail }}</small></p>
            <i></i>
          </button>
        </div>
      </div>
      <div class="context-row">
        <label>服务用户<el-input :model-value="userId" :disabled="!canSwitchUser" @update:model-value="emit('update:userId', $event)" /></label>
        <label>会话线程<el-input :model-value="threadId" @update:model-value="emit('update:threadId', $event)" /></label>
      </div>
      <label class="query-box">
        <span>告诉智能体需要处理什么</span>
        <el-input
          :model-value="query"
          type="textarea"
          :rows="7"
          maxlength="2000"
          show-word-limit
          placeholder="输入订单、物流、政策或退款问题…"
          @update:model-value="emit('update:query', $event)"
          @keyup.ctrl.enter="emit('send')"
        />
      </label>
      <div class="quick-prompts">
        <span>快速指令</span>
        <button v-for="prompt in quickPrompts" :key="prompt" type="button" @click="emit('update:query', prompt)">{{ prompt }}</button>
      </div>
      <button class="primary-command" type="button" :disabled="loading || !query.trim()" @click="emit('send')">
        <el-icon><Promotion /></el-icon><span>{{ loading ? '协同链路运行中…' : '运行多智能体流程' }}</span><kbd>Ctrl ↵</kbd>
      </button>

      <div v-if="result" :class="['result-card', { warning: pending }]">
        <header><span><el-icon><component :is="pending ? Warning : CircleCheck" /></el-icon></span><div><small>{{ result.intent || 'unknown' }}</small><strong>{{ pending ? '等待人工审批' : '任务处理完成' }}</strong></div></header>
        <p>{{ result.response }}</p>
      </div>

      <div v-if="pending && canApprove" class="human-gate">
        <div class="gate-title"><span>HUMAN-IN-THE-LOOP</span><strong>敏感操作确认</strong></div>
        <div class="context-row">
          <label>审批人<el-input :model-value="reviewer" @update:model-value="emit('update:reviewer', $event)" /></label>
          <label>审批意见<el-input :model-value="approvalReason" @update:model-value="emit('update:approvalReason', $event)" /></label>
        </div>
        <div class="gate-actions">
          <el-button type="success" @click="emit('decide', true)"><el-icon><CircleCheck /></el-icon>批准并恢复</el-button>
          <el-button type="danger" plain @click="emit('decide', false)"><el-icon><Delete /></el-icon>拒绝操作</el-button>
        </div>
      </div>
    </section>

    <aside class="workbench-side">
      <section class="panel trace-panel">
        <header class="panel-header"><div><span class="section-kicker">LIVE TRACE</span><h3>执行轨迹</h3></div><span class="live-indicator"><i></i>实时</span></header>
        <div v-if="liveNodes.length" class="trace-list">
          <div v-for="(item, index) in liveNodes" :key="`${item.node}-${index}`" class="trace-item">
            <span>{{ index + 1 }}</span><div><strong>{{ item.node }}</strong><p>{{ item.message }}</p></div>
          </div>
        </div>
        <div v-else class="trace-placeholder"><div class="trace-skeleton" v-for="index in 4" :key="index"><span></span><i></i></div><p>运行任务后，这里将逐步显示路由、检索、工具和审批节点。</p></div>
      </section>

      <section class="panel evidence-panel">
        <header class="panel-header"><div><span class="section-kicker">EVIDENCE</span><h3>政策证据</h3></div><span v-if="result?.evidence_level" class="evidence-level">{{ result.evidence_level }}</span></header>
        <div v-if="result?.evidence?.length" class="evidence-list">
          <article v-for="item in result.evidence" :key="`${item.source}-${item.section}`">
            <div><strong>{{ item.section }}</strong><b>{{ Math.round(item.score * 100) }}%</b></div>
            <p>{{ item.content }}</p><small>{{ item.source }}#{{ item.section }}</small>
          </article>
        </div>
        <div v-else class="empty-copy">涉及政策判断时，系统会在这里呈现条款级来源与检索置信度。</div>
      </section>
    </aside>
  </div>
</template>
