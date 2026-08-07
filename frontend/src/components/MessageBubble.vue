<script setup lang="ts">
import { computed, h } from 'vue'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  RobotOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { Bubble } from 'ant-design-x-vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import type { ChatMessage } from '@/api/chat'
import InterruptCard from './InterruptCard.vue'

const props = defineProps<{ message: ChatMessage }>()

const renderedContent = computed(() => {
  if (props.message.kind !== 'assistant' || !props.message.content) {
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

const toolStatus = computed(() => {
  if (props.message.status === 'error') return 'Failed'
  if (props.message.status === 'success') return 'Completed'
  return 'Running'
})

const toolIcon = computed(() => {
  if (props.message.status === 'error') return CloseCircleOutlined
  if (props.message.status === 'success') return CheckCircleOutlined
  return LoadingOutlined
})

const formattedArgs = computed(() => {
  if (!props.message.toolArgs || Object.keys(props.message.toolArgs).length === 0) return ''
  try {
    return JSON.stringify(props.message.toolArgs, null, 2)
  } catch {
    return String(props.message.toolArgs)
  }
})
</script>

<template>
  <div v-if="message.kind === 'tool_call'" class="tool-message tool-call-message">
    <div class="tool-title">
      <ToolOutlined />
      <code>{{ message.toolName || 'tool' }}</code>
      <span class="tool-status" :class="message.status">
        <component :is="toolIcon" />
        {{ toolStatus }}
      </span>
    </div>
    <span v-if="message.actorName" class="actor-name">{{ message.actorName }}</span>
    <pre v-if="formattedArgs" class="tool-payload">{{ formattedArgs }}</pre>
  </div>

  <div v-else-if="message.kind === 'tool_result'" class="tool-message tool-result-message">
    <div class="tool-title">
      <ToolOutlined />
      <span>{{ message.toolName || 'Tool result' }}</span>
      <span class="tool-status" :class="message.status">
        {{ message.status === 'error' ? 'Failed' : 'Completed' }}
      </span>
    </div>
    <pre class="tool-payload">{{ message.content }}</pre>
  </div>

  <Bubble
    v-else
    :placement="message.role === 'user' ? 'end' : 'start'"
    :loading="message.loading"
    :avatar="avatar"
  >
    <template #message>
      <span v-if="message.actorName && message.role === 'assistant'" class="actor-name">
        {{ message.actorName }}
      </span>
      <InterruptCard v-if="message.interrupted" :interrupt="message.interrupted" />
      <div
        v-if="message.content"
        class="bubble-text"
        :class="{ 'markdown-body': message.role === 'assistant' }"
        v-html="renderedContent"
      />
    </template>
  </Bubble>
</template>

<style scoped>
.tool-message {
  width: min(680px, 100%);
  padding: 10px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fff;
}

.tool-result-message {
  border-color: #b7eb8f;
  background: #fcfff5;
}

.tool-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 22px;
  color: #434343;
  font-size: 13px;
}

.tool-title code {
  color: #262626;
  font-size: 12px;
}

.tool-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  color: #1677ff;
  font-size: 12px;
}

.tool-status.success { color: #389e0d; }
.tool-status.error { color: #cf1322; }
.tool-status.running :deep(.anticon) { animation: spin 1s linear infinite; }

.actor-name {
  display: inline-block;
  margin-bottom: 6px;
  color: #8c8c8c;
  font-size: 11px;
}

.tool-payload {
  max-height: 240px;
  overflow: auto;
  margin: 8px 0 0;
  padding: 8px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  background: #fafafa;
  color: #434343;
  font-family: Consolas, Monaco, monospace;
  font-size: 11px;
  line-height: 1.45;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.markdown-body :deep(p) { margin: 0 0 8px; line-height: 1.7; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; margin: 4px 0 8px; }
.markdown-body :deep(li) { margin: 2px 0; line-height: 1.6; }
.markdown-body :deep(strong) { font-weight: 600; }
.markdown-body :deep(code) {
  padding: 1px 5px;
  border-radius: 3px;
  background: #f0f2f5;
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
}
.markdown-body :deep(pre) {
  overflow-x: auto;
  margin: 8px 0;
  padding: 12px;
  border-radius: 6px;
  background: #1e1e1e;
  color: #d4d4d4;
}
.markdown-body :deep(pre code) { padding: 0; background: none; color: inherit; }
.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding-left: 12px;
  border-left: 3px solid #1677ff;
  color: #595959;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
