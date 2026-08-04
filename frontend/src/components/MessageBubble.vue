<script setup lang="ts">
import { h, computed } from 'vue'
import { Bubble } from 'ant-design-x-vue'
import { RobotOutlined, UserOutlined } from '@ant-design/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ChatMessage } from '@/api/chat'
import AgentNodeCards from './AgentNodeCards.vue'
import InterruptCard from './InterruptCard.vue'

const props = withDefaults(
  defineProps<{ message: ChatMessage; showExecution?: boolean }>(),
  { showExecution: false },
)

// Markdown 渲染（仅对 assistant 消息）
const renderedContent = computed(() => {
  if (props.message.role === 'user' || !props.message.content) {
    return props.message.content
  }
  try {
    const raw = marked.parse(props.message.content, { async: false }) as string
    return DOMPurify.sanitize(raw, {
      ALLOWED_TAGS: [
        'p', 'br', 'strong', 'em', 'u', 'code', 'pre', 'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'a', 'span',
      ],
      ALLOWED_ATTR: ['href', 'class'],
    })
  } catch {
    return props.message.content
  }
})

const avatar = computed(() =>
  props.message.role === 'user'
    ? { icon: h(UserOutlined) }
    : { icon: h(RobotOutlined), style: { background: '#1677ff' } },
)
</script>

<template>
  <div class="message-bubble-wrapper">
    <Bubble
      :placement="message.role === 'user' ? 'end' : 'start'"
      :loading="message.loading && !message.executionNodes?.length"
      :avatar="avatar"
    >
      <template #message>
        <AgentNodeCards
          v-if="showExecution && message.executionNodes?.length"
          :nodes="message.executionNodes"
        />

        <!-- HITL 提示卡 -->
        <InterruptCard
          v-if="message.interrupted"
          :interrupt="message.interrupted"
        />

        <!-- 文字内容：user 原文 / assistant Markdown 渲染 -->
        <div
          v-if="message.content"
          class="bubble-text"
          :class="{ 'markdown-body': message.role === 'assistant' }"
          v-html="renderedContent"
        />

        <!-- assistant 纯 loading 状态（还未收到任何内容）-->
        <span v-else-if="message.loading" class="loading-dots">
          <span /><span /><span />
        </span>
      </template>
    </Bubble>
  </div>
</template>

<style scoped>
.message-bubble-wrapper {
  width: 100%;
}

/* ── Markdown 渲染基础样式 ── */
.markdown-body :deep(p) {
  margin: 0 0 8px;
  line-height: 1.7;
}
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 4px 0 8px;
}
.markdown-body :deep(li) { margin: 2px 0; line-height: 1.6; }
.markdown-body :deep(strong) { font-weight: 600; }
.markdown-body :deep(code) {
  background: #f0f2f5;
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}
.markdown-body :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
}
.markdown-body :deep(blockquote) {
  border-left: 3px solid #1677ff;
  padding-left: 12px;
  margin: 8px 0;
  color: #595959;
}

/* 三点 loading 动画（无文字时） */
.loading-dots {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  height: 20px;
}
.loading-dots span {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: #1677ff;
  border-radius: 50%;
  animation: bounce 1.2s ease-in-out infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}
</style>
