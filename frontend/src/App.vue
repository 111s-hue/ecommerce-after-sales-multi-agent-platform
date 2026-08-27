<script setup lang="ts">
import { Bell, Compass, Document, Search } from '@element-plus/icons-vue'
import { defineAsyncComponent, onMounted, onUnmounted, ref } from 'vue'
import AppSidebar from './components/AppSidebar.vue'
import TopBar from './components/TopBar.vue'
import { useConsole } from './composables/useConsole'
import LoginView from './views/LoginView.vue'

const ApprovalsView = defineAsyncComponent(() => import('./views/ApprovalsView.vue'))
const AuditView = defineAsyncComponent(() => import('./views/AuditView.vue'))
const ConversationsView = defineAsyncComponent(() => import('./views/ConversationsView.vue'))
const InsightsView = defineAsyncComponent(() => import('./views/InsightsView.vue'))
const KnowledgeView = defineAsyncComponent(() => import('./views/KnowledgeView.vue'))
const OperationsView = defineAsyncComponent(() => import('./views/OperationsView.vue'))
const OverviewView = defineAsyncComponent(() => import('./views/OverviewView.vue'))
const WorkbenchView = defineAsyncComponent(() => import('./views/WorkbenchView.vue'))

const state = useConsole()
const sidebarCollapsed = ref(localStorage.getItem('after-sales-sidebar-collapsed') === 'true')
const searchOpen = ref(false)
const notificationsOpen = ref(false)
const helpOpen = ref(false)
const lastSearchTerm = ref('')

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('after-sales-sidebar-collapsed', String(sidebarCollapsed.value))
}

async function openSearch(term: string) {
  lastSearchTerm.value = term
  searchOpen.value = true
  await state.globalSearch(term)
}

async function openNotifications() {
  notificationsOpen.value = true
  await state.loadNotifications()
}

function activateSearchResult(result: (typeof state.searchResults.value)[number]) {
  if (result.operationTab) state.operationTab.value = result.operationTab
  if (result.suggestedQuery) state.query.value = result.suggestedQuery
  state.activeView.value = result.view
  searchOpen.value = false
}

function handleShortcut(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    document.querySelector<HTMLInputElement>('[aria-label="全局搜索"]')?.focus()
  }
}

onMounted(() => window.addEventListener('keydown', handleShortcut))
onUnmounted(() => window.removeEventListener('keydown', handleShortcut))
</script>

<template>
  <LoginView
    v-if="!state.token.value"
    v-model:username="state.loginUser.value"
    v-model:password="state.loginPassword.value"
    :loading="state.loading.value"
    :error="state.error.value"
    @submit="state.signIn"
    @clear-error="state.error.value = ''"
  />

  <div v-else :class="['app-shell', { 'sidebar-collapsed': sidebarCollapsed }]">
    <AppSidebar
      :active-view="state.activeView.value"
      :pending-count="state.pendingCount.value"
      :system-info="state.systemInfo.value"
      :role="state.loginRole.value"
      :collapsed="sidebarCollapsed"
      @navigate="state.activeView.value = $event"
      @toggle="toggleSidebar"
    />

    <main class="main-stage">
      <TopBar
        :title="state.pageMeta.value.title"
        :description="state.pageMeta.value.description"
        :login-role="state.loginRole.value"
        :loading="state.refreshing.value"
        :unread-count="state.unreadCount.value"
        :sidebar-collapsed="sidebarCollapsed"
        @refresh="state.refreshCurrentView"
        @sign-out="state.signOut"
        @toggle-sidebar="toggleSidebar"
        @search="openSearch"
        @notifications="openNotifications"
        @help="helpOpen = true"
      />

      <el-alert
        v-if="state.error.value"
        :title="state.error.value"
        type="error"
        show-icon
        closable
        class="global-alert"
        @close="state.error.value = ''"
      />

      <el-alert
        v-if="state.notice.value"
        :title="state.notice.value"
        type="success"
        show-icon
        closable
        class="global-alert"
        @close="state.notice.value = ''"
      />

      <div class="view-container" v-loading="state.refreshing.value" element-loading-text="正在同步业务数据…">
        <OverviewView
          v-if="state.activeView.value === 'overview'"
          :summary="state.summary.value"
          :approvals="state.approvals.value"
          :conversations="state.conversations.value"
          :system-info="state.systemInfo.value"
          @navigate="state.activeView.value = $event"
          @apply-strategy="state.startSuggestedTask"
        />
        <WorkbenchView
          v-else-if="state.activeView.value === 'workbench'"
          :user-id="state.userId.value"
          :thread-id="state.threadId.value"
          :selected-agent="state.selectedAgent.value"
          :query="state.query.value"
          :reviewer="state.reviewer.value"
          :approval-reason="state.approvalReason.value"
          :loading="state.loading.value"
          :result="state.result.value"
          :live-nodes="state.liveNodes.value"
          :pending="state.pending.value"
          :can-approve="state.canApproveCurrent.value"
          :can-switch-user="state.loginRole.value !== 'customer'"
          @update:userId="state.userId.value = $event"
          @update:threadId="state.threadId.value = $event"
          @update:selectedAgent="state.selectedAgent.value = $event"
          @update:query="state.query.value = $event"
          @update:reviewer="state.reviewer.value = $event"
          @update:approvalReason="state.approvalReason.value = $event"
          @send="state.sendMessage"
          @decide="state.decide($event)"
          @reset="state.newConversation"
        />
        <ApprovalsView
          v-else-if="state.activeView.value === 'approvals'"
          :approvals="state.approvals.value"
          :loading="state.loading.value"
          @decide="state.decide"
        />
        <OperationsView
          v-else-if="state.activeView.value === 'operations'"
          :orders="state.orders.value"
          :after-sales="state.afterSales.value"
          :user-id="state.userId.value"
          :role="state.loginRole.value"
          :permissions="state.loginPermissions.value"
          :loading="state.loading.value"
          :active-tab="state.operationTab.value"
          @update:activeTab="state.operationTab.value = $event"
          @create-case="state.createAfterSale"
          @review-case="state.reviewAfterSale($event.caseId, $event.approved)"
          @execute-refund="state.executeRefund($event.caseId, $event.refundId)"
          @complete-case="state.completeAfterSale"
        />
        <ConversationsView
          v-else-if="state.activeView.value === 'conversations'"
          :conversations="state.conversations.value"
        />
        <KnowledgeView
          v-else-if="state.activeView.value === 'knowledge'"
          :documents="state.documents.value"
          :upload-file="state.uploadFile.value"
          :loading="state.loading.value"
          :can-publish="state.canPublishKnowledgeCurrent.value"
          :preview="state.knowledgePreview.value"
          @update:uploadFile="state.uploadFile.value = $event"
          @upload="state.uploadDocument"
          @preview-document="state.previewDocument"
          @download-document="state.downloadDocument"
          @delete-document="state.deleteDocument"
          @rebuild="state.rebuildKnowledge"
          @clear-preview="state.knowledgePreview.value = null"
        />
        <AuditView
          v-else-if="state.activeView.value === 'audit'"
          :audits="state.audits.value"
        />
        <InsightsView
          v-else
          :evaluation="state.evaluation.value"
          :summary="state.summary.value"
          :system-info="state.systemInfo.value"
        />
      </div>
    </main>

    <el-dialog v-model="searchOpen" title="全局搜索" width="min(680px, 92vw)" class="action-dialog" destroy-on-close>
      <div v-loading="state.searchLoading.value" class="search-results" aria-live="polite">
        <div class="action-dialog-summary"><el-icon><Search /></el-icon><span>“{{ lastSearchTerm }}”的搜索结果</span><b>{{ state.searchResults.value.length }} 项</b></div>
        <button
          v-for="item in state.searchResults.value"
          :key="item.id"
          type="button"
          class="search-result"
          @click="activateSearchResult(item)"
        >
          <span><el-icon><Document /></el-icon></span>
          <p><b>{{ item.title }}</b><small>{{ item.description }}</small></p>
          <em>{{ item.kind }}</em>
        </button>
        <el-empty v-if="!state.searchLoading.value && !state.searchResults.value.length" description="没有匹配结果，请尝试订单号、客户账号或业务关键词" :image-size="72" />
      </div>
    </el-dialog>

    <el-drawer v-model="notificationsOpen" title="通知中心" size="min(420px, 94vw)" class="notification-drawer">
      <div class="notification-summary"><el-icon><Bell /></el-icon><span>未读通知</span><b>{{ state.unreadCount.value }}</b></div>
      <div v-if="state.notifications.value.length" class="notification-list">
        <article v-for="item in state.notifications.value" :key="item.notification_id" :class="{ unread: !item.read_at }">
          <span></span>
          <div><strong>{{ item.subject || '售后业务通知' }}</strong><small>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</small></div>
          <button v-if="!item.read_at" type="button" @click="state.markNotificationRead(item.notification_id)">标为已读</button>
          <em v-else>已读</em>
        </article>
      </div>
      <el-empty v-else description="暂无通知" :image-size="86" />
    </el-drawer>

    <el-dialog v-model="helpOpen" title="帮助中心" width="min(620px, 92vw)" class="action-dialog">
      <div class="help-grid">
        <article><el-icon><Compass /></el-icon><div><b>从哪里开始</b><p>在“智能体协同”中输入客户问题并运行流程；高风险退款会自动进入“人工审批”。</p></div></article>
        <article><el-icon><Search /></el-icon><div><b>全局搜索</b><p>可搜索真实订单、售后工单、会话、智能体和知识文档；按 Ctrl + K 可快速唤起。</p></div></article>
        <article><el-icon><Document /></el-icon><div><b>业务闭环</b><p>在“工单中心”完成售后创建、审核、退款执行和履约关闭，所有关键操作都会写入审计记录。</p></div></article>
      </div>
    </el-dialog>
  </div>
</template>
