<script setup lang="ts">
import { ChatLineRound } from '@element-plus/icons-vue'
import type { Conversation } from '../types'
defineProps<{ conversations: Conversation[] }>()
</script>

<template>
  <section class="panel table-panel">
    <header class="panel-header"><div><span class="section-kicker">CONVERSATION HISTORY</span><h3>全量会话</h3></div><span class="table-count">{{ conversations.length }} 条记录</span></header>
    <el-table :data="conversations" class="enterprise-table" empty-text="暂无会话记录">
      <el-table-column label="问题摘要" min-width="280"><template #default="scope"><div class="conversation-cell"><span><el-icon><ChatLineRound /></el-icon></span><div><strong>{{ scope.row.title }}</strong><small>{{ scope.row.thread_id }}</small></div></div></template></el-table-column>
      <el-table-column prop="user_id" label="用户" width="110" />
      <el-table-column label="识别意图" min-width="130"><template #default="scope"><span class="action-chip">{{ scope.row.intent || '待识别' }}</span></template></el-table-column>
      <el-table-column label="处理状态" min-width="130"><template #default="scope"><span :class="['status-pill', scope.row.status]"><i></i>{{ scope.row.status === 'completed' ? '已完成' : scope.row.status === 'pending_approval' ? '待审批' : scope.row.status }}</span></template></el-table-column>
      <el-table-column label="最后更新" min-width="190"><template #default="scope">{{ new Date(scope.row.updated_at).toLocaleString('zh-CN') }}</template></el-table-column>
    </el-table>
  </section>
</template>
