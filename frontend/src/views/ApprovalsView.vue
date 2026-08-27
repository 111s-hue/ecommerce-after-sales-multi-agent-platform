<script setup lang="ts">
import { CircleCheck, CloseBold, Clock } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import type { Approval } from '../types'

const props = defineProps<{ approvals: Approval[]; loading: boolean }>()
const emit = defineEmits<{ decide: [approved: boolean, threadId: string] }>()
const filter = ref('pending')
const filtered = computed(() => filter.value === 'all' ? props.approvals : props.approvals.filter((item) => item.status === filter.value))
const counts = computed(() => ({
  pending: props.approvals.filter((item) => item.status === 'pending').length,
  approved: props.approvals.filter((item) => item.status === 'approved').length,
  rejected: props.approvals.filter((item) => item.status === 'rejected').length,
}))
</script>

<template>
  <div class="view-stack">
    <section class="approval-summary">
      <button v-for="item in [
        { key: 'pending', label: '待处理', count: counts.pending },
        { key: 'approved', label: '已批准', count: counts.approved },
        { key: 'rejected', label: '已拒绝', count: counts.rejected },
      ]" :key="item.key" :class="{ active: filter === item.key }" type="button" @click="filter = item.key">
        <span>{{ item.label }}</span><strong>{{ item.count }}</strong>
      </button>
      <button :class="{ active: filter === 'all' }" type="button" @click="filter = 'all'"><span>全部任务</span><strong>{{ approvals.length }}</strong></button>
    </section>

    <section class="panel table-panel">
      <header class="panel-header"><div><span class="section-kicker">RISK DECISIONS</span><h3>审批任务</h3></div><span class="table-count">{{ filtered.length }} 条记录</span></header>
      <el-table :data="filtered" class="enterprise-table" empty-text="当前筛选条件下没有审批任务">
        <el-table-column label="业务对象" min-width="190">
          <template #default="scope"><div class="cell-primary"><strong>{{ scope.row.order_id }}</strong><small>{{ scope.row.thread_id }}</small></div></template>
        </el-table-column>
        <el-table-column label="申请人" prop="user_id" width="110" />
        <el-table-column label="操作类型" min-width="130"><template #default><span class="action-chip">退款申请</span></template></el-table-column>
        <el-table-column label="影响金额" min-width="120"><template #default="scope"><strong class="money">¥{{ Number(scope.row.amount).toFixed(2) }}</strong></template></el-table-column>
        <el-table-column label="状态" min-width="120">
          <template #default="scope"><span :class="['status-pill', scope.row.status]"><i></i>{{ scope.row.status === 'pending' ? '待审批' : scope.row.status === 'approved' ? '已批准' : '已拒绝' }}</span></template>
        </el-table-column>
        <el-table-column label="发起时间" min-width="170"><template #default="scope">{{ new Date(scope.row.created_at).toLocaleString('zh-CN') }}</template></el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="scope">
            <div v-if="scope.row.status === 'pending'" class="inline-actions">
              <el-button type="success" size="small" :loading="loading" @click="emit('decide', true, scope.row.thread_id)"><el-icon><CircleCheck /></el-icon>批准</el-button>
              <el-button type="danger" plain size="small" :loading="loading" @click="emit('decide', false, scope.row.thread_id)"><el-icon><CloseBold /></el-icon>拒绝</el-button>
            </div>
            <span v-else class="decision-by"><el-icon><Clock /></el-icon>{{ scope.row.reviewer || '系统' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>
