<script setup lang="ts">
import {
  Delete, DocumentAdd, Download, Files, Refresh, UploadFilled, View,
} from '@element-plus/icons-vue'
import { ref } from 'vue'
import type { KnowledgeDocument, KnowledgePreview } from '../types'

defineProps<{
  documents: KnowledgeDocument[]
  uploadFile: File | null
  loading: boolean
  canPublish: boolean
  preview: KnowledgePreview | null
}>()
const emit = defineEmits<{
  'update:uploadFile': [file: File | null]
  upload: []
  previewDocument: [filename: string]
  downloadDocument: [filename: string]
  deleteDocument: [filename: string]
  rebuild: []
  clearPreview: []
}>()
const deleteCandidate = ref<KnowledgeDocument | null>(null)

function onFile(event: Event) {
  emit('update:uploadFile', (event.target as HTMLInputElement).files?.[0] || null)
}

function confirmDelete() {
  if (!deleteCandidate.value) return
  emit('deleteDocument', deleteCandidate.value.name)
  deleteCandidate.value = null
}
</script>

<template>
  <div class="knowledge-grid">
    <section class="panel upload-panel">
      <span class="section-kicker">KNOWLEDGE INGESTION</span>
      <div class="upload-icon"><el-icon><DocumentAdd /></el-icon></div>
      <h3>{{ canPublish ? '发布政策文档' : '知识库只读访问' }}</h3>
      <p>{{ canPublish ? '上传 Markdown 后将自动切分条款、重建混合索引，并同步到智能体运行时。' : '审批主管可以查看政策语料与索引状态，发布和重建操作仅对系统管理员开放。' }}</p>
      <label v-if="canPublish" class="file-drop">
        <input :key="uploadFile?.name || 'empty'" type="file" accept=".md,text/markdown" @change="onFile" />
        <el-icon><UploadFilled /></el-icon>
        <strong>{{ uploadFile?.name || '选择 Markdown 文件' }}</strong>
        <small>单个文件不超过 2 MB</small>
      </label>
      <el-button v-if="canPublish" type="primary" :disabled="!uploadFile" :loading="loading" @click="emit('upload')">上传并发布索引</el-button>
      <div class="governance-note"><strong>{{ canPublish ? '发布保护' : '权限说明' }}</strong><span>{{ canPublish ? '仅管理员可写入；原文与索引版本保持一致。' : '当前账号不会显示或触发任何知识库写入操作。' }}</span></div>
    </section>

    <section class="panel table-panel">
      <header class="panel-header">
        <div><span class="section-kicker">POLICY CORPUS</span><h3>在库文档</h3></div>
        <div class="knowledge-header-actions">
          <span class="table-count">{{ documents.length }} 份文档</span>
          <el-button v-if="canPublish" :loading="loading" @click="emit('rebuild')"><el-icon><Refresh /></el-icon>重建索引</el-button>
        </div>
      </header>
      <div v-if="documents.length" class="document-list">
        <article v-for="document in documents" :key="document.name">
          <span><el-icon><Files /></el-icon></span>
          <div><strong>{{ document.name }}</strong><small>v{{ document.version_no || 1 }} · {{ (document.size / 1024).toFixed(1) }} KB · {{ document.storage }}</small></div>
          <time>{{ new Date(document.updated_at).toLocaleDateString('zh-CN') }}</time>
          <span class="index-state"><i></i>索引有效</span>
          <div class="document-actions">
            <button type="button" title="查看文档" @click="emit('previewDocument', document.name)"><el-icon><View /></el-icon><span>查看</span></button>
            <button type="button" title="下载文档" @click="emit('downloadDocument', document.name)"><el-icon><Download /></el-icon><span>下载</span></button>
            <button v-if="canPublish" class="danger" type="button" title="删除文档" @click="deleteCandidate = document"><el-icon><Delete /></el-icon><span>删除</span></button>
          </div>
        </article>
      </div>
      <el-empty v-else description="知识库中还没有政策文档" />
    </section>

    <el-dialog :model-value="!!preview" title="知识文档预览" width="min(760px, 92vw)" @update:model-value="!$event && emit('clearPreview')">
      <div v-if="preview" class="knowledge-preview">
        <header><div><strong>{{ preview.name }}</strong><small>{{ (preview.size / 1024).toFixed(1) }} KB · Markdown</small></div><el-button @click="emit('downloadDocument', preview.name)"><el-icon><Download /></el-icon>下载原文</el-button></header>
        <pre>{{ preview.content }}</pre>
      </div>
    </el-dialog>

    <el-dialog :model-value="!!deleteCandidate" title="删除知识文档" width="min(460px, 92vw)" @update:model-value="!$event && (deleteCandidate = null)">
      <div v-if="deleteCandidate" class="delete-confirmation">
        <span><el-icon><Delete /></el-icon></span>
        <div><strong>确认删除“{{ deleteCandidate.name }}”吗？</strong><p>文档将立即从智能体运行索引中移除；数据库中的历史版本和治理记录仍会保留。</p></div>
      </div>
      <template #footer><el-button @click="deleteCandidate = null">取消</el-button><el-button type="danger" :loading="loading" @click="confirmDelete">确认删除</el-button></template>
    </el-dialog>
  </div>
</template>
