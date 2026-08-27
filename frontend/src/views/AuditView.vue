<script setup lang="ts">
import type { AuditLog } from '../types'
defineProps<{ audits: AuditLog[] }>()
</script>

<template>
  <section class="panel table-panel">
    <header class="panel-header"><div><span class="section-kicker">IMMUTABLE TRAIL</span><h3>工具与安全审计</h3></div><span class="table-count">最近 {{ audits.length }} 条</span></header>
    <el-table :data="audits" class="enterprise-table" empty-text="暂无审计记录">
      <el-table-column label="动作" min-width="180"><template #default="scope"><div class="cell-primary"><strong>{{ scope.row.action }}</strong><small>{{ scope.row.resource }}</small></div></template></el-table-column>
      <el-table-column prop="user_id" label="用户" width="100" />
      <el-table-column label="会话线程" prop="thread_id" min-width="180" show-overflow-tooltip />
      <el-table-column label="结果" min-width="120"><template #default="scope"><span :class="['status-pill', scope.row.outcome]"><i></i>{{ scope.row.outcome }}</span></template></el-table-column>
      <el-table-column prop="detail" label="详情" min-width="260" show-overflow-tooltip />
      <el-table-column label="发生时间" min-width="190"><template #default="scope">{{ new Date(scope.row.created_at).toLocaleString('zh-CN') }}</template></el-table-column>
    </el-table>
  </section>
</template>
