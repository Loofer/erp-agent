<script setup lang="ts">
import { computed, defineAsyncComponent, h } from 'vue'
import {
  ApartmentOutlined,
  RobotOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { Bubble } from 'ant-design-x-vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import type { ChatMessage } from '@/api/chat'
import { parseMessageSegments } from '@/visualization/chart'
import InterruptCard from './InterruptCard.vue'

const ChartCard = defineAsyncComponent(() => import('./analysis/ChartCard.vue'))

const props = defineProps<{ message: ChatMessage }>()

const contentSegments = computed(() => {
  if (props.message.kind !== 'assistant') return []
  if (props.message.namespace?.length) {
    return [{ type: 'markdown' as const, content: props.message.content }]
  }
  return parseMessageSegments(props.message.content)
})

function renderMarkdown(content: string): string {
  try {
    const raw = marked.parse(content, { async: false }) as string
    return DOMPurify.sanitize(raw, {
      ALLOWED_TAGS: [
        'p', 'br', 'strong', 'em', 'u', 'code', 'pre', 'ul', 'ol', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'a', 'span',
      ],
      ALLOWED_ATTR: ['href', 'class'],
    })
  } catch {
    return content
  }
}

const avatar = computed(() =>
  props.message.role === 'user'
    ? { icon: h(UserOutlined) }
    : { icon: h(RobotOutlined), style: { background: '#1677ff' } },
)

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
  <div v-if="message.kind === 'agent_routing'" class="tool-message routing-message">
    <div class="tool-title"><ApartmentOutlined /><strong>Agent Routing</strong></div>
    <dl class="tool-details">
      <template v-if="message.actorName"><dt>Agent Name</dt><dd>{{ message.actorName }}</dd></template>
      <template v-if="message.targetAgent"><dt>Target Agent</dt><dd><code>{{ message.targetAgent }}</code></dd></template>
      <template v-if="message.description"><dt>Description</dt><dd><pre class="tool-payload">{{ message.description }}</pre></dd></template>
    </dl>
  </div>

  <div v-else-if="message.kind === 'tool_call'" class="tool-message tool-call-message">
    <div class="tool-title">
      <ToolOutlined />
      <strong>Tool Call Start</strong>
    </div>
    <dl class="tool-details">
      <template v-if="message.actorName"><dt>Agent Name</dt><dd>{{ message.actorName }}</dd></template>
      <dt>Tool Name</dt><dd><code>{{ message.toolName || 'tool' }}</code></dd>
      <template v-if="formattedArgs"><dt>Args</dt><dd><pre class="tool-payload">{{ formattedArgs }}</pre></dd></template>
    </dl>
  </div>

  <div v-else-if="message.kind === 'tool_result'" class="tool-message tool-result-message">
    <div class="tool-title">
      <ToolOutlined />
      <strong>Tool Call End</strong>
    </div>
    <dl class="tool-details">
      <template v-if="message.actorName"><dt>Agent Name</dt><dd>{{ message.actorName }}</dd></template>
      <dt>Tool Name</dt><dd><code>{{ message.toolName || 'tool' }}</code></dd>
      <dt>Result</dt><dd><pre class="tool-payload result-payload">{{ message.content }}</pre></dd>
    </dl>
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
      <template v-if="message.role === 'assistant'">
        <template v-for="(segment, index) in contentSegments" :key="`${message.id}:${index}`">
          <div
            v-if="segment.type === 'markdown' && segment.content"
            class="bubble-text markdown-body"
            v-html="renderMarkdown(segment.content)"
          />
          <ChartCard v-else-if="segment.type === 'chart'" :chart="segment.chart" />
        </template>
      </template>
      <div v-else-if="message.content" class="bubble-text">{{ message.content }}</div>
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
  border-color: #d9d9d9;
}

.routing-message {
  border-color: #91caff;
  background: #f5faff;
}

.tool-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 22px;
  color: #434343;
  font-size: 13px;
}

.tool-title code, .tool-title strong {
  color: #262626;
  font-size: 12px;
}

.actor-name {
  display: inline-block;
  margin-bottom: 6px;
  color: #8c8c8c;
  font-size: 11px;
}

.tool-details {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 7px 10px;
  margin: 10px 0 0;
  font-size: 12px;
}

.tool-details dt { color: #8c8c8c; }
.tool-details dd { min-width: 0; margin: 0; color: #434343; }

.tool-payload {
  max-height: 360px;
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

@media (max-width: 720px) {
  .tool-details { grid-template-columns: 1fr; gap: 3px; }
}
</style>
