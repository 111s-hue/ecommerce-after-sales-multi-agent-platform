<script setup lang="ts">
import {
  Bell, Calendar, Menu, QuestionFilled, Refresh, Search, SwitchButton, User,
} from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import type { Role } from '../types'

const props = defineProps<{
  title: string
  description: string
  loginRole: Role
  loading: boolean
  unreadCount: number
  sidebarCollapsed: boolean
}>()
const emit = defineEmits<{
  refresh: []
  signOut: []
  toggleSidebar: []
  search: [term: string]
  notifications: []
  help: []
}>()
const roleLabel = computed(() => ({ admin: '系统管理员', approver: '审批主管', customer: '客户账号' })[props.loginRole])
const searchTerm = ref('')

function submitSearch() {
  if (searchTerm.value.trim()) emit('search', searchTerm.value.trim())
}
</script>

<template>
  <header class="topbar">
    <div class="global-nav">
      <button class="menu-button" type="button" :title="sidebarCollapsed ? '展开菜单' : '收起菜单'" :aria-expanded="!sidebarCollapsed" @click="emit('toggleSidebar')"><el-icon><Menu /></el-icon></button>
      <div class="global-nav-spacer"></div>
      <div class="tenant-switch" aria-label="当前企业"><span>优品在线（北京）科技有限公司</span></div>
      <form class="global-search" role="search" @submit.prevent="submitSearch">
        <input v-model="searchTerm" type="search" aria-label="全局搜索" placeholder="搜索工单、客户、智能体、知识库..." />
        <button type="submit" aria-label="执行全局搜索" :disabled="!searchTerm.trim()"><el-icon><Search /></el-icon></button>
      </form>
      <button class="utility-button notification-button" type="button" aria-label="打开通知中心" @click="emit('notifications')"><el-icon><Bell /></el-icon><em v-if="unreadCount">{{ unreadCount > 99 ? '99+' : unreadCount }}</em></button>
      <button class="utility-button" type="button" title="帮助中心" aria-label="打开帮助中心" @click="emit('help')"><el-icon><QuestionFilled /></el-icon></button>
      <div class="identity-chip">
        <span class="avatar"><el-icon><User /></el-icon><i></i></span>
        <span><b>{{ roleLabel }}</b><small>已认证会话</small></span>
      </div>
      <button class="signout-button" type="button" title="退出登录" @click="emit('signOut')"><el-icon><SwitchButton /></el-icon></button>
    </div>

    <div class="page-toolbar">
      <div class="page-heading">
        <h1>{{ title }} <small aria-hidden="true">i</small></h1>
        <span>{{ description }}</span>
      </div>
      <div class="topbar-actions">
        <div class="date-button" aria-label="当前数据范围"><el-icon><Calendar /></el-icon><span>实时数据</span></div>
        <button class="refresh-button" type="button" :disabled="loading" title="刷新当前页面数据" @click="emit('refresh')">
          <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>
          <span>{{ loading ? '同步中' : '刷新' }}</span>
        </button>
      </div>
    </div>
  </header>
</template>
