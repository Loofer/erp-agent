<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { ToolCall } from '@/types/agent'

const props = defineProps<{ tool: ToolCall }>()

const expanded = ref(false)
const elapsed = ref(0)
let intervalId: number | undefined

// 计算耗时
const duration = computed(() => {
  if (props.tool.endedAt && props.tool.startedAt) {
    return ((props.tool.endedAt - props.tool.startedAt) / 1000).toFixed(1)
  }
  if (props.tool.status === 'running' && props.tool.startedAt) {
    return ((elapsed.value - props.tool.startedAt) / 1000).toFixed(1)
  }
  return null
})

// 状态图标
const statusIcon = computed(() => {
  switch (props.tool.status) {
    case 'pending':
      return '○'
    case 'running':
      return '⟳'
    case 'success':
      return '✅'
    case 'error':
      return '❌'
  }
})

// 运行中时实时更新计时器
onMounted(() => {
  if (props.tool.status === 'running') {
    intervalId = window.setInterval(() => {
      elapsed.value = Date.now()
    }, 100)
  }
})

onUnmounted(() => {
  if (intervalId !== undefined) clearInterval(intervalId)
})

// 格式化参数和结果
const formattedArgs = computed(() => {
  try {
    return JSON.stringify(props.tool.args, null, 2)
  } catch {
    return String(props.tool.args)
  }
})

const formattedResult = computed(() => {
  if (!props.tool.result) return ''
  // 截断长结果（前 2000 字符）
  const content = props.tool.result
  const limit = 2000
  if (content.length > limit) {
    return content.slice(0, limit) + `\n... (省略 ${content.length - limit} 字符)`
  }
  try {
    const parsed = JSON.parse(content)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return content
  }
})
</script>

<template>
  <div class="tool-call-item">
    <div class="tool-call-header" @click="expanded = !expanded">
      <span class="icon">{{ statusIcon }}</span>
      <span class="name">{{ tool.name }}</span>
      <span v-if="duration" class="duration">{{ duration }}s</span>
      <span v-if="tool.status === 'running'" class="running-hint">...</span>
      <span v-if="tool.isEvicted" class="evicted-badge">结果已卸载</span>
      <span class="expand-toggle">{{ expanded ? '▾' : '▸' }}</span>
    </div>

    <div v-if="expanded" class="tool-call-details">
      <div class="detail-section">
        <div class="detail-label">参数：</div>
        <pre class="detail-content">{{ formattedArgs }}</pre>
      </div>
      <div v-if="tool.result" class="detail-section">
        <div class="detail-label">返回：</div>
        <pre class="detail-content">{{ formattedResult }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool-call-item {
  border-left: 2px solid #d9d9d9;
  padding-left: 12px;
  margin: 4px 0;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 0;
  user-select: none;
}

.icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.name {
  font-family: 'Consolas', 'Monaco', monospace;
  font-weight: 500;
  color: #1677ff;
}

.duration {
  color: #8c8c8c;
  font-size: 12px;
}

.running-hint {
  color: #1677ff;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%,
  50% {
    opacity: 1;
  }
  50.1%,
  100% {
    opacity: 0.3;
  }
}

.evicted-badge {
  background: #fff7e6;
  border: 1px solid #ffd591;
  color: #d46b08;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.expand-toggle {
  margin-left: auto;
  color: #8c8c8c;
}

.tool-call-details {
  margin-top: 8px;
  padding: 8px;
  background: #fafafa;
  border-radius: 4px;
  font-size: 12px;
}

.detail-section {
  margin-bottom: 8px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-label {
  color: #8c8c8c;
  margin-bottom: 4px;
}

.detail-content {
  margin: 0;
  padding: 8px;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  overflow-x: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px;
  line-height: 1.4;
}
</style>
