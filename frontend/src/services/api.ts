import axios from 'axios'
import type { ChatResult, LiveNode } from '../types'
import { createRequestId } from './requestId'

const apiBase = import.meta.env.VITE_API_BASE || '/api/v1'

export const api = axios.create({
  baseURL: apiBase,
  timeout: 15_000,
})

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('after-sales-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['X-Request-ID'] = createRequestId()
  return config
})

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    return typeof detail === 'string' ? detail : error.message
  }
  return error instanceof Error ? error.message : '请求处理失败，请稍后重试'
}

export async function streamChat(
  payload: { user_id: string; thread_id: string; query: string; target_agent: string },
  onNode: (node: LiveNode) => void,
): Promise<ChatResult> {
  const token = sessionStorage.getItem('after-sales-token')
  const response = await fetch(`${apiBase}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': createRequestId(),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok || !response.body) {
    const body = await response.text()
    try {
      const parsed = JSON.parse(body)
      throw new Error(parsed.detail || '智能体运行服务不可用')
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error(body || '智能体运行服务不可用')
      throw error
    }
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: ChatResult | null = null
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() || ''
    for (const frame of frames) {
      let event = 'message'
      let data = '{}'
      for (const line of frame.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7)
        if (line.startsWith('data: ')) data = line.slice(6)
      }
      const parsed = JSON.parse(data)
      if (event === 'node') {
        onNode({
          node: parsed.node,
          message: parsed.trace?.[0]?.message || parsed.response || '节点执行完成',
        })
      }
      if (event === 'result') result = parsed
    }
  }
  if (!result) throw new Error('运行已结束，但未收到完整结果')
  return result
}
