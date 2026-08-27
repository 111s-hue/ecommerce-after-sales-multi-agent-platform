<script setup lang="ts">
import {
  Aim, ChatDotRound, CircleCheck, Collection, DataAnalysis, DocumentChecked,
  Grid, List, Operation, Tickets,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { computed } from 'vue'
import { canAccessView } from '../security/permissions'
import type { Role, SystemInfo, ViewKey } from '../types'

const props = defineProps<{ activeView: ViewKey; pendingCount: number; systemInfo: SystemInfo | null; role: Role; collapsed: boolean }>()
const emit = defineEmits<{ navigate: [view: ViewKey]; toggle: [] }>()

const groups: { label: string; items: { key: ViewKey; label: string; icon: Component }[] }[] = [
  {
    label: '指挥中心',
    items: [
      { key: 'overview', label: '总览驾驶舱', icon: Grid },
      { key: 'workbench', label: '智能体协同', icon: Aim },
      { key: 'approvals', label: '人工审批', icon: CircleCheck },
    ],
  },
  {
    label: '业务运营',
    items: [
      { key: 'operations', label: '工单中心', icon: Tickets },
      { key: 'conversations', label: '会话质检', icon: ChatDotRound },
      { key: 'knowledge', label: '知识库', icon: Collection },
    ],
  },
  {
    label: '治理与质量',
    items: [
      { key: 'audit', label: '规则审计', icon: List },
      { key: 'insights', label: '数据分析', icon: DataAnalysis },
    ],
  },
]

const visibleGroups = computed(() => groups
  .map((group) => ({ ...group, items: group.items.filter((item) => canAccessView(props.role, item.key)) }))
  .filter((group) => group.items.length > 0))
</script>

<template>
  <aside :class="['sidebar', { collapsed }]">
    <div class="brand">
      <div class="brand-mark"><el-icon><Operation /></el-icon></div>
      <div><strong>电商售后多智能体平台</strong><span>AFTER-SALES AGENT HUB</span></div>
    </div>

    <nav class="side-nav" aria-label="主导航">
      <section v-for="group in visibleGroups" :key="group.label" class="nav-group">
        <p>{{ group.label }}</p>
        <button
          v-for="item in group.items"
          :key="item.key"
          type="button"
          :class="['nav-item', { active: activeView === item.key }]"
          :title="collapsed ? item.label : undefined"
          @click="emit('navigate', item.key)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
          <em v-if="item.key === 'approvals' && pendingCount">{{ pendingCount }}</em>
        </button>
      </section>
    </nav>

    <div v-if="role !== 'customer'" class="system-card">
      <div class="system-line"><i></i><span>服务运行中</span><b>{{ systemInfo?.version || 'v1.0' }}</b></div>
      <div class="system-meta">
        <span><el-icon><DocumentChecked /></el-icon>{{ systemInfo?.rag.backend || 'hybrid-lite' }}</span>
        <span>{{ systemInfo?.environment || 'development' }}</span>
      </div>
    </div>
    <button class="collapse-button" type="button" :aria-label="collapsed ? '展开菜单' : '收起菜单'" @click="emit('toggle')">
      <span class="collapse-glyph">{{ collapsed ? '›' : '‹' }}</span><span>{{ collapsed ? '展开菜单' : '收起菜单' }}</span>
    </button>
  </aside>
</template>
