<script setup lang="ts">
import { useChatStore } from '@/stores/chat'

const store = useChatStore()
</script>

<template>
  <div class="hitl-approval-bar">
    <a-button type="primary" size="large" @click="store.resumeApprove()">
      ✅ 批准执行
    </a-button>
    <a-button danger size="large" @click="store.resumeReject()">
      ❌ 取消操作
    </a-button>
  </div>
</template>

<style scoped>
.hitl-approval-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 16px 32px 20px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
}

.hitl-approval-bar :deep(.ant-btn) {
  min-width: 140px;
  height: 44px;
  font-size: 15px;
}
</style>
