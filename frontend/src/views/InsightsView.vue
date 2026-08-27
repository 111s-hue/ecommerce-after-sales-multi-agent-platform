<script setup lang="ts">
import { Cpu, DataLine, Finished, Search } from '@element-plus/icons-vue'
import type { Evaluation, Summary, SystemInfo } from '../types'
defineProps<{ evaluation: Evaluation; summary: Summary; systemInfo: SystemInfo | null }>()
</script>

<template>
  <div class="view-stack">
    <section class="quality-hero panel">
      <div><span class="section-kicker">QUALITY CONTROL</span><h2>让每次发布，都有数据可依。</h2><p>离线回归覆盖路由、越权、提示注入、政策检索和审批恢复；运行指标用于观察真实业务健康度。</p></div>
      <div class="quality-score"><small>任务成功率</small><strong>{{ Math.round(Number(evaluation.task_success_rate || 0) * 100) }}<em>%</em></strong><span>{{ evaluation.passed || 0 }} / {{ evaluation.total || 0 }} 用例通过</span></div>
    </section>
    <section class="quality-grid">
      <article class="panel quality-stat"><span><el-icon><Finished /></el-icon></span><div><small>意图准确率</small><strong>{{ Math.round(Number(evaluation.intent_accuracy || 0) * 100) }}%</strong></div></article>
      <article class="panel quality-stat"><span><el-icon><Cpu /></el-icon></span><div><small>模型运行模式</small><strong>{{ systemInfo?.llm.enabled ? 'LLM 在线' : '确定性降级' }}</strong></div></article>
      <article class="panel quality-stat"><span><el-icon><Search /></el-icon></span><div><small>检索后端</small><strong>{{ systemInfo?.rag.backend || 'hybrid-lite' }}</strong></div></article>
      <article class="panel quality-stat"><span><el-icon><DataLine /></el-icon></span><div><small>累计工具调用</small><strong>{{ summary.tool_calls || 0 }}</strong></div></article>
    </section>
    <section class="panel table-panel">
      <header class="panel-header"><div><span class="section-kicker">REGRESSION SUITE</span><h3>评测用例明细</h3></div><span v-if="evaluation.status === 'not_run'" class="status-pill pending"><i></i>尚未运行</span></header>
      <div v-if="evaluation.status === 'not_run'" class="evaluation-empty"><code>python -m scripts.evaluate</code><p>{{ evaluation.message || '运行评测脚本后将在此展示结果。' }}</p></div>
      <el-table v-else :data="evaluation.details || []" class="enterprise-table">
        <el-table-column prop="id" label="用例" min-width="160" />
        <el-table-column prop="actual_intent" label="实际意图" min-width="130" />
        <el-table-column prop="actual_status" label="实际状态" min-width="130" />
        <el-table-column label="结果" min-width="110"><template #default="scope"><span :class="['status-pill', scope.row.passed ? 'success' : 'blocked']"><i></i>{{ scope.row.passed ? '通过' : '失败' }}</span></template></el-table-column>
      </el-table>
    </section>
  </div>
</template>
