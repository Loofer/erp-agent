<script setup lang="ts">
import { computed } from 'vue'
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ToolOutlined,
} from '@ant-design/icons-vue'
import type { AgentNode, ToolCall } from '@/types/agent'

const props = defineProps<{ nodes: AgentNode[] }>()

function nodeTitle(node: AgentNode): string {
  return node.namespace.length === 0 ? '主 Agent' : node.agentName || 'Subagent'
}

function statusIcon(tool: ToolCall) {
  if (tool.status === 'success') return CheckCircleOutlined
  if (tool.status === 'error') return CloseCircleOutlined
  return LoadingOutlined
}

function statusText(tool: ToolCall): string {
  if (tool.status === 'success') return '已完成'
  if (tool.status === 'error') return '执行失败'
  return '执行中'
}

function formatValue(value: unknown): string {
  if (value === undefined || value === null || value === '') return ''
  try {
    const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
    return text.length > 1600 ? `${text.slice(0, 1600)}\n...` : text
  } catch {
    return String(value)
  }
}

const visibleNodes = computed(() =>
  props.nodes.filter((node) => node.content || node.toolCalls.length > 0),
)
</script>

<template>
  <div class="agent-nodes">
    <section v-for="node in visibleNodes" :key="node.id" class="agent-node-card">
      <header class="node-header">
        <ApartmentOutlined class="node-icon" />
        <div class="node-heading">
          <strong>{{ nodeTitle(node) }}</strong>
          <span>{{ node.namespace.length === 0 ? '工具节点' : '代理节点' }}</span>
        </div>
      </header>

      <div v-if="node.content" class="node-output">{{ node.content }}</div>

      <div v-if="node.toolCalls.length" class="tool-list">
        <div v-for="tool in node.toolCalls" :key="tool.id" class="tool-row">
          <div class="tool-summary">
            <ToolOutlined />
            <code>{{ tool.name }}</code>
            <span class="tool-status" :class="tool.status">
              <component :is="statusIcon(tool)" />
              {{ statusText(tool) }}
            </span>
          </div>
          <div v-if="Object.keys(tool.args).length" class="tool-detail">
            <span>参数</span>
            <pre>{{ formatValue(tool.args) }}</pre>
          </div>
          <div v-if="tool.result && !tool.isDelegation" class="tool-detail">
            <span>结果</span>
            <pre>{{ formatValue(tool.result) }}</pre>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.agent-nodes {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
  width: min(680px, 100%);
}

.agent-node-card {
  overflow: hidden;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fff;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 11px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

.node-icon {
  color: #1677ff;
  font-size: 16px;
}

.node-heading {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.node-heading strong {
  overflow: hidden;
  color: #262626;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-heading span {
  color: #8c8c8c;
  font-size: 11px;
}

.node-output {
  max-height: 220px;
  overflow: auto;
  padding: 10px 11px;
  border-bottom: 1px solid #f0f0f0;
  color: #434343;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.tool-list {
  display: grid;
}

.tool-row {
  padding: 9px 11px;
  border-bottom: 1px solid #f0f0f0;
}

.tool-row:last-child {
  border-bottom: 0;
}

.tool-summary {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 22px;
  color: #595959;
}

.tool-summary code {
  color: #262626;
  font-size: 12px;
}

.tool-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  color: #1677ff;
  font-size: 11px;
  white-space: nowrap;
}

.tool-status.success { color: #389e0d; }
.tool-status.error { color: #cf1322; }
.tool-status.running :deep(.anticon),
.tool-status.pending :deep(.anticon) { animation: spin 1s linear infinite; }

@keyframes spin {
  to { transform: rotate(360deg); }
}

.tool-detail {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 8px;
  margin-top: 7px;
  color: #8c8c8c;
  font-size: 11px;
}

.tool-detail pre {
  max-height: 160px;
  overflow: auto;
  margin: 0;
  padding: 7px 8px;
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

@media (max-width: 720px) {
  .tool-detail {
    grid-template-columns: 1fr;
  }
}
</style>
