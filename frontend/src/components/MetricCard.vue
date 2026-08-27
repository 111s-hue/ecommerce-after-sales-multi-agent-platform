<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  label: string
  value: string | number
  note: string
  delta: string
  icon: Component
  tone?: 'green' | 'amber' | 'blue' | 'slate' | 'teal' | 'purple'
}>()
</script>

<template>
  <article :class="['metric-card', `tone-${tone || 'blue'}`]">
    <div class="metric-main">
      <span class="metric-icon"><el-icon><component :is="icon" /></el-icon></span>
      <div><small>{{ label }}</small><strong>{{ value }}</strong></div>
    </div>
    <div class="metric-foot"><span>{{ note }}</span><b>{{ delta }}</b></div>
    <svg class="metric-spark" viewBox="0 0 180 34" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 27 L12 29 L25 23 L38 28 L52 16 L66 25 L78 21 L92 11 L106 22 L119 8 L132 17 L146 5 L159 11 L172 1 L180 3" />
    </svg>
  </article>
</template>
