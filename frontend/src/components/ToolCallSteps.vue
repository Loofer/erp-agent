<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCall } from '@/types/agent'
import ToolCallItem from './ToolCallItem.vue'

const props = defineProps<{ toolCalls: ToolCall[] }>()

const expanded = ref(false)

const isRunning = computed(() => props.toolCalls.some((t) => t.status === 'running'))
const isDone = computed(() => props.toolCalls.every((t) => t.status !== 'running' && t.status !== 'pending'))

const title = computed(() => {
  if (!isDone.value) return '正在执行...'
  const count = props.toolCalls.length
  return count === 1 ? '已调用工具' : `已执行 ${count} 个步骤`
})
</script>

<template>
  <div class="tool-call-steps">
    <!-- 头部：标题 + 展开/收起按钮 -->
    <div class="steps-header" @click="expanded = !expanded">
      <span v-if="isRunning" class="running-spinner" />
      <span class="steps-title">{{ title }}</span>
      <button class="toggle-btn">{{ expanded ? '收起 ▲' : '展开详情 ▸' }}</button>
    </div>

    <!-- 收起时：显示所有工具名小标签 -->
    <div v-if="!expanded" class="steps-summary">
      <span
        v-for="tc in toolCalls"
        :key="tc.id"
        class="summary-pill"
        :class="tc.status"
      >
        <span class="pill-icon">
          {{ tc.status === 'success' ? '✅' : tc.status === 'error' ? '❌' : tc.status === 'running' ? '⟳' : '○' }}
        </span>
        {{ tc.name }}
      </span>
    </div>

    <!-- 展开时：显示每一步详情 -->
    <div v-if="expanded" class="steps-list">
      <ToolCallItem v-for="tc in toolCalls" :key="tc.id" :tool="tc" />
    </div>
  </div>
</template>

<style scoped>
.tool-call-steps {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fafafa;
  padding: 10px 14px;
  margin-bottom: 10px;
}

.steps-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.running-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid #1677ff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.steps-title {
  font-size: 13px;
  font-weight: 500;
  color: #595959;
}

.toggle-btn {
  margin-left: auto;
  background: none;
  border: none;
  color: #1677ff;
  font-size: 12px;
  cursor: pointer;
  padding: 2px 6px;
}

.toggle-btn:hover {
  text-decoration: underline;
}

.steps-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.summary-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 12px;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  color: #595959;
}

.summary-pill.success { border-color: #b7eb8f; background: #f6ffed; }
.summary-pill.error   { border-color: #ffa39e; background: #fff1f0; }
.summary-pill.running { border-color: #91caff; background: #e6f4ff; color: #1677ff; }

.steps-list {
  margin-top: 10px;
}
</style>
