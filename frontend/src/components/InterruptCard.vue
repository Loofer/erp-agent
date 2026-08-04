<script setup lang="ts">
import { computed } from 'vue'
import type { InterruptData } from '@/types/agent'

const props = defineProps<{ interrupt: InterruptData }>()

const isApproval = computed(() => props.interrupt.interrupt_mode === 'approval')

const detailText = computed(() => {
  if (!props.interrupt.actions.length) return ''
  try {
    return JSON.stringify(
      props.interrupt.actions.map(({ name, args, description }) => ({
        tool: name,
        description,
        args,
      })),
      null,
      2,
    )
  } catch {
    return ''
  }
})
</script>

<template>
  <div class="interrupt-card" :class="interrupt.interrupt_mode">
    <!-- 头部 -->
    <div class="interrupt-header">
      <span class="interrupt-icon">{{ isApproval ? '⚠️' : '💬' }}</span>
      <span class="interrupt-title">{{ isApproval ? '需要您的确认' : '需要补充信息' }}</span>
    </div>

    <!-- 审批型：展示操作详情 -->
    <template v-if="isApproval && detailText">
      <pre class="interrupt-detail">{{ detailText }}</pre>
    </template>

    <!-- 输入型：展示提示文字 -->
    <template v-else-if="!isApproval && interrupt.hint">
      <p class="interrupt-hint">{{ interrupt.hint }}</p>
    </template>
  </div>
</template>

<style scoped>
.interrupt-card {
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 8px;
  border: 1px solid;
}

.interrupt-card.approval {
  background: #fffbe6;
  border-color: #ffe58f;
}

.interrupt-card.input {
  background: #e6f4ff;
  border-color: #91caff;
}

.interrupt-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.interrupt-title {
  font-weight: 600;
  font-size: 14px;
  color: #262626;
}

.interrupt-detail {
  margin: 0;
  padding: 8px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.interrupt-hint {
  margin: 0;
  font-size: 13px;
  color: #0958d9;
  line-height: 1.6;
}
</style>
