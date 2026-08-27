<script setup lang="ts">
import {
  Aim, ArrowRight, ChatDotRound, CircleCheck, Clock, Collection, Connection,
  DataAnalysis, Document, Grid, Operation, Search, Tickets, User,
} from '@element-plus/icons-vue'
import { computed } from 'vue'
import MetricCard from '../components/MetricCard.vue'
import type { Approval, Conversation, Summary, SystemInfo, ViewKey } from '../types'

const props = defineProps<{
  summary: Summary
  approvals: Approval[]
  conversations: Conversation[]
  systemInfo: SystemInfo | null
}>()
const emit = defineEmits<{ navigate: [view: ViewKey]; applyStrategy: [query: string] }>()

const statusLabel: Record<string, string> = {
  completed: '已完成', pending_approval: '待审批', running: '处理中',
}
const pendingApprovals = computed(() => props.approvals.filter((item) => item.status === 'pending'))
const completedConversations = computed(() => props.conversations.filter((item) => item.status === 'completed').length)
const phases = [
  ['1', '任务分发', '接收工单与意图识别'],
  ['2', '意图识别', '识别客户问题类型'],
  ['3', '知识检索', '检索政策与历史方案'],
  ['4', '策略决策', '制定处理策略与路由'],
  ['5', '执行反馈', '执行并收集结果反馈'],
  ['6', '闭环分析', '质检分析与优化闭环'],
]
const hotSpots = [
  ['退款申请', 100], ['物流延迟', 76], ['商品破损', 61],
  ['错发漏发', 45], ['发票问题', 31], ['售后规则', 18],
]
</script>

<template>
  <div class="view-stack overview-view">
    <section class="metric-grid">
      <MetricCard label="今日协同会话" :value="summary.conversations || 0" note="实时" delta="持续更新" :icon="Tickets" tone="blue" />
      <MetricCard label="自动闭环率" :value="`${summary.automation_rate || 0}%`" note="策略执行" delta="运行稳定" :icon="CircleCheck" tone="teal" />
      <MetricCard label="知识检索深度" :value="`Top ${systemInfo?.rag.top_k || 4}`" note="混合检索" delta="索引在线" :icon="Search" tone="purple" />
      <MetricCard label="待审批任务" :value="summary.pending_approvals || 0" note="人工闸门" delta="需要关注" :icon="User" tone="amber" />
      <MetricCard label="安全拦截" :value="summary.blocked_requests || 0" note="策略防护" delta="实时生效" :icon="Grid" tone="green" />
      <MetricCard label="在线智能体" value="4 / 4" note="协作集群" delta="全部在线" :icon="Connection" tone="blue" />
    </section>

    <section class="dashboard-middle">
      <article class="panel orchestration-board">
        <header class="panel-header">
          <div><h3>多智能体协同流程 <small aria-hidden="true">i</small></h3><span>实时任务编排与节点状态</span></div>
          <button type="button" @click="emit('navigate', 'workbench')"><el-icon><Operation /></el-icon> 查看编排配置</button>
        </header>

        <div class="phase-strip">
          <div v-for="phase in phases" :key="phase[0]">
            <b>{{ phase[0] }}</b><span><strong>{{ phase[1] }}</strong><small>{{ phase[2] }}</small></span><i></i>
          </div>
        </div>

        <div class="agent-topology" aria-label="售后多智能体实时协作拓扑">
          <svg class="topology-lines" viewBox="0 0 1000 260" preserveAspectRatio="none" aria-hidden="true">
            <defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>
            <path class="main-flow" d="M130 130 H150 M290 130 H310 M450 130 H480 V60 H500 M450 130 H480 V200 H500 M620 60 H680 M620 60 H650 V160 H680 M620 200 H650 V160 H680 M800 60 H820 V130 H840 M800 160 H840" />
            <path class="data-flow" d="M450 142 H470 V212 H500 M620 72 H665 V148 H680" />
          </svg>

          <div class="flow-node intake"><span><el-icon><ChatDotRound /></el-icon></span><div><b>客户咨询</b><small>渠道接入</small></div></div>
          <div class="flow-node orchestrator"><span><el-icon><Operation /></el-icon></span><div><b>编排智能体</b><small>运行中</small></div></div>
          <div class="flow-node diagnosis"><span><el-icon><Aim /></el-icon></span><div><b>问题诊断智能体</b><small>运行中</small></div></div>
          <div class="flow-node order"><span><el-icon><Tickets /></el-icon></span><div><b>订单校验智能体</b><small>运行中</small></div></div>
          <div class="flow-node logistics"><span><el-icon><Connection /></el-icon></span><div><b>物流查询智能体</b><small>运行中</small></div></div>
          <div class="flow-node refund"><span><el-icon><Collection /></el-icon></span><div><b>退款策略智能体</b><small>运行中</small></div></div>
          <div class="flow-node expert"><span><el-icon><User /></el-icon></span><div><b>升级专员智能体</b><small>待处理 {{ pendingApprovals.length }}</small></div></div>
          <div class="flow-node quality"><span><el-icon><DataAnalysis /></el-icon></span><div><b>质检分析智能体</b><small>运行中</small></div></div>
        </div>

        <footer class="flow-legend">
          <span><i class="solid"></i>主流程</span><span><i class="dashed"></i>辅助流程</span>
          <span><i class="teal"></i>数据流</span><span><i class="orange"></i>人工介入</span>
          <button type="button" @click="emit('navigate', 'workbench')">发起协同任务 <el-icon><ArrowRight /></el-icon></button>
        </footer>
      </article>

      <aside class="panel status-board">
        <header class="panel-header"><div><h3>实时告警与工单状态</h3><span>关键节点动态</span></div><button type="button" @click="emit('navigate', 'approvals')">查看全部</button></header>
        <div class="alert-list">
          <div><em class="high">高</em><span>敏感退款等待人工确认</span><time>刚刚</time></div>
          <div><em class="middle">中</em><span>知识检索索引状态正常</span><time>2 分钟前</time></div>
          <div><em class="middle">中</em><span>智能体协作链路已同步</span><time>5 分钟前</time></div>
          <div><em class="low">低</em><span>质检规则运行稳定</span><time>8 分钟前</time></div>
        </div>
        <div class="status-distribution">
          <div class="distribution-title"><strong>工单状态分布</strong><span>总数 {{ conversations.length }}</span></div>
          <div class="distribution-body">
            <div class="donut-chart"><span>{{ conversations.length ? Math.round(completedConversations / conversations.length * 100) : 0 }}%</span></div>
            <div class="donut-legend">
              <p><i class="processing"></i><span>处理中</span><b>{{ Math.max(conversations.length - completedConversations, 0) }}</b></p>
              <p><i class="completed"></i><span>已完成</span><b>{{ completedConversations }}</b></p>
              <p><i class="pending"></i><span>待审批</span><b>{{ pendingApprovals.length }}</b></p>
            </div>
          </div>
        </div>
      </aside>
    </section>

    <section class="overview-bottom">
      <article class="panel queue-panel">
        <header class="panel-header"><div><h3>工单处理队列 <small aria-hidden="true">i</small></h3><span>最近进入协同链路的任务</span></div><button type="button" @click="emit('navigate', 'conversations')">更多 <el-icon><ArrowRight /></el-icon></button></header>
        <div v-if="conversations.length" class="queue-table">
          <div class="queue-head"><span>工单编号</span><span>客户</span><span>问题类型</span><span>状态</span><span>责任智能体</span><span>更新时间</span></div>
          <div v-for="item in conversations.slice(0, 5)" :key="item.thread_id" class="queue-row">
            <code>{{ item.thread_id.slice(0, 14) }}</code><span>{{ item.user_id }}</span><span>{{ item.intent || '待识别' }}</span>
            <span><em :class="['status-pill', item.status]">{{ statusLabel[item.status] || item.status }}</em></span>
            <span>{{ item.intent === 'logistics' ? '物流查询智能体' : '编排智能体' }}</span><time>{{ new Date(item.updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</time>
          </div>
        </div>
        <div v-else class="empty-compact"><el-icon><Document /></el-icon><p>暂无会话，去工作台发起第一个任务。</p></div>
      </article>

      <article class="panel hotspot-panel">
        <header class="panel-header"><div><h3>客户问题热点</h3><span>TOP 6</span></div></header>
        <div class="hotspot-list">
          <div v-for="item in hotSpots" :key="item[0]"><span>{{ item[0] }}</span><i><b :style="{ width: `${item[1]}%` }"></b></i><em>{{ item[1] }}</em></div>
        </div>
      </article>

      <article class="panel strategy-panel">
        <header class="panel-header"><div><h3>智能建议与处理策略</h3><span>基于实时运行数据</span></div></header>
        <div class="strategy-list">
          <div><span><el-icon><CircleCheck /></el-icon></span><p><b>自动补发建议</b><small>识别物流异常，优先建议补发处理</small></p><button type="button" @click="emit('applyStrategy', '查询订单物流异常，核验后优先生成补发处理方案')">应用</button></div>
          <div><span><el-icon><Clock /></el-icon></span><p><b>触发退款审核</b><small>符合退款策略，建议快速进入审批</small></p><button type="button" @click="emit('applyStrategy', '核验当前订单退款资格，并在符合政策时发起退款审批')">应用</button></div>
          <div><span><el-icon><Collection /></el-icon></span><p><b>同步物流异常说明</b><small>检测到物流延迟，建议发送安抚话术</small></p><button type="button" @click="emit('applyStrategy', '查询物流延迟原因，并生成面向客户的异常说明与安抚方案')">应用</button></div>
        </div>
      </article>

      <article class="panel quality-panel">
        <header class="panel-header"><div><h3>会话质检摘要</h3><span>实时</span></div></header>
        <div class="quality-summary">
          <div><small>合规率</small><strong>95.2%</strong><em>↑ 稳定</em></div>
          <div><small>风险会话数</small><strong>{{ summary.blocked_requests || 0 }}</strong><em>实时拦截</em></div>
          <div><small>负面情绪占比</small><strong>6.3%</strong><em>↓ 可控</em></div>
        </div>
        <div class="runtime-mini">
          <p><span>模型运行时</span><b>{{ systemInfo?.llm.enabled ? systemInfo.llm.model : '确定性降级模式' }}</b></p>
          <p><span>知识检索</span><b>{{ systemInfo?.rag.backend || 'hybrid-lite' }}</b></p>
          <p><span>服务版本</span><b>{{ systemInfo?.version || '1.0.0' }}</b></p>
        </div>
      </article>
    </section>
  </div>
</template>
