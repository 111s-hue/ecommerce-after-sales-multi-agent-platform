<script setup lang="ts">
import { ArrowRight, CircleCheck, Lock, Operation, User } from '@element-plus/icons-vue'

defineProps<{ loading: boolean; error: string }>()
const username = defineModel<string>('username', { required: true })
const password = defineModel<string>('password', { required: true })
const emit = defineEmits<{ submit: []; clearError: [] }>()

</script>

<template>
  <main class="login-shell">
    <section class="login-story">
      <div class="login-brand">
        <span><el-icon><Operation /></el-icon></span>
        <div><strong>电商售后多智能体平台</strong><small>AFTER-SALES AGENT HUB</small></div>
      </div>

      <div class="login-thesis">
        <span class="login-kicker">ENTERPRISE AGENT ORCHESTRATION</span>
        <h1>一站式售后协同，<br />让每个工单高效闭环。</h1>
        <p>统一接入订单、物流、政策、退款与质检智能体。自动分派、实时协作、人工把关，关键动作全程可追溯。</p>
      </div>

      <div class="login-route" aria-label="售后智能体可信执行链路">
        <div class="login-route-line"></div>
        <div class="login-route-node active"><span>S</span><b>识别</b><small>Supervisor</small></div>
        <div class="login-route-node"><span>A</span><b>查证</b><small>专业智能体</small></div>
        <div class="login-route-node human"><span>H</span><b>确认</b><small>人工闸门</small></div>
        <div class="login-route-node done"><span><el-icon><CircleCheck /></el-icon></span><b>执行</b><small>幂等写入</small></div>
      </div>

      <footer><span>LANGGRAPH</span><i></i><span>AGENTIC RAG</span><i></i><span>HUMAN-IN-THE-LOOP</span></footer>
    </section>

    <section class="login-entry">
      <div class="login-form-wrap">
        <div class="login-form-head">
          <span>SECURE CONSOLE</span>
          <h2>欢迎登录</h2>
          <p>电商售后多智能体协同平台</p>
        </div>

        <el-alert
          v-if="error"
          :title="error"
          type="error"
          show-icon
          closable
          class="login-alert"
          @close="emit('clearError')"
        />

        <form class="login-form" @submit.prevent="emit('submit')">
          <label>
            <span>账号</span>
            <el-input
              v-model="username"
              size="large"
              autocomplete="username"
              placeholder="请输入企业账号"
              @input="emit('clearError')"
            >
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </label>
          <label>
            <span>密码</span>
            <el-input
              v-model="password"
              size="large"
              type="password"
              autocomplete="current-password"
              show-password
              placeholder="请输入登录密码"
              @input="emit('clearError')"
            >
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </label>
          <button class="login-submit" type="submit" :disabled="loading || !username.trim() || !password">
            <span>{{ loading ? '正在验证身份…' : '进入控制台' }}</span>
            <el-icon :class="{ 'login-arrow-loading': loading }"><ArrowRight /></el-icon>
          </button>
        </form>

        <p class="login-security"><el-icon><Lock /></el-icon>账号权限由组织管理员统一配置，连续登录失败会触发安全锁定。</p>
      </div>
    </section>
  </main>
</template>
