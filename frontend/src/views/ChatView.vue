<script setup lang="ts">
import { h, ref, computed, nextTick, onMounted } from 'vue'
import { Conversations, Sender } from 'ant-design-x-vue'
import type { ConversationsProps } from 'ant-design-x-vue'
import { PlusOutlined, RobotOutlined, StopOutlined, ToolOutlined } from '@ant-design/icons-vue'
import { useChatStore } from '@/stores/chat'
import MessageBubble from '@/components/MessageBubble.vue'
import HitlApprovalBar from '@/components/HitlApprovalBar.vue'
import ChartCard from '@/components/analysis/ChartCard.vue'
import ReportMarkdown from '@/components/analysis/ReportMarkdown.vue'

const store = useChatStore()
const inputValue = ref('')
const messagesEndRef = ref<HTMLDivElement | null>(null)
const showToolResults = ref(false)

const visibleMessages = computed(() =>
  store.messages.filter(
    (message) =>
      !['agent_routing', 'tool_call', 'tool_result'].includes(message.kind) ||
      showToolResults.value,
  ),
)

onMounted(() => {
  store.loadHistory()
})

async function scrollToBottom() {
  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
}

// 判断是否处于输入型 HITL（用户可输入以提供补充数据）
const isInputHitl = computed(
  () => store.pendingInterrupt?.interrupt_mode === 'input',
)

// 是否处于审批型 HITL（输入框被隐藏，改为两个按钮）
const isApprovalHitl = computed(
  () => store.pendingInterrupt?.interrupt_mode === 'approval',
)

// 输入型 HITL 时的 placeholder
const senderPlaceholder = computed(() => {
  if (isInputHitl.value) {
    return store.pendingInterrupt?.hint || '请输入补充信息…'
  }
  return '输入消息，按 Enter 发送…'
})

async function handleSend(val: string) {
  if (!val.trim() || store.loading) return
  inputValue.value = ''

  if (isInputHitl.value) {
    await store.resumeInput(val.trim())
  } else {
    await store.sendMessage(val.trim())
  }
  scrollToBottom()
}

const conversationMenuConfig: ConversationsProps['menu'] = () => ({
  items: [{ key: 'delete', label: '删除', danger: true }],
})
</script>

<template>
  <div class="chat-layout">
    <!-- 左侧：会话历史侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="logo-title">ERP Agent</span>
        <a-button type="text" :icon="h(PlusOutlined)" @click="store.newConversation" title="新建对话" />
      </div>

      <div class="sidebar-body">
        <Conversations
          :items="store.conversations"
          :active-key="store.currentThreadId ?? undefined"
          :menu="conversationMenuConfig"
          @activeChange="(key: string) => store.selectConversation(key)"
        />
        <div v-if="store.conversations.length === 0" class="empty-tip">
          暂无历史对话
        </div>
      </div>
    </aside>

    <!-- 右侧：聊天区域 -->
    <main class="chat-panel">
      <!-- 消息列表 -->
      <div class="messages-area">
        <div v-if="store.messages.length === 0" class="welcome-hint">
          <RobotOutlined class="welcome-icon" />
          <p>你好！我是 ERP 智能助手，请输入您的问题开始对话。</p>
        </div>

        <template v-else>
          <div
            v-for="msg in visibleMessages"
            :key="msg.id"
            class="bubble-row"
            :class="msg.kind"
          >
            <MessageBubble :message="msg" />
          </div>
        </template>

        <section v-if="store.analysisSummary" class="analysis-summary">
          <div class="analysis-summary-header">
            <strong>采购分析</strong><a-tag>{{ store.analysisSummary.status }}</a-tag>
          </div>
          <div class="analysis-metrics">
            <span>样本数：{{ store.analysisSummary.sample_size }}</span>
            <span v-for="metric in store.analysisSummary.metrics" :key="metric.name">
              {{ metric.name }}：{{ metric.value }}{{ metric.unit ? ` ${metric.unit}` : '' }}
            </span>
          </div>
          <a-alert v-if="store.analysisSummary.data_gaps.length || store.analysisSummary.error" type="warning" show-icon>
            {{ store.analysisSummary.error || store.analysisSummary.data_gaps.join('；') }}
          </a-alert>
        </section>
        <ChartCard v-for="chart in store.charts" :key="chart.spec?.id || chart.reason" :chart="chart" />
        <ReportMarkdown v-if="store.report" :markdown="store.report" />

        <div ref="messagesEndRef" />
      </div>

      <!-- 底部输入区：审批型 HITL → 两个按钮；其余 → Sender -->
      <HitlApprovalBar v-if="isApprovalHitl" />
      <div v-else class="input-area">
        <div class="sender-toolbar">
          <ToolOutlined />
          <span>Show tool calls</span>
          <a-switch v-model:checked="showToolResults" size="small" />
        </div>
        <!-- 取消按钮（流进行中时显示） -->
        <div v-if="store.loading" class="cancel-bar">
          <a-button
            type="text"
            size="small"
            :icon="h(StopOutlined)"
            @click="store.cancelStream()"
          >
            停止生成
          </a-button>
        </div>
        <!-- 输入型 HITL 时顶部提示条 -->
        <div v-if="isInputHitl" class="input-hitl-hint">
          💬 {{ store.pendingInterrupt?.hint || '请补充所需信息以继续操作' }}
        </div>
        <Sender
          v-model:value="inputValue"
          :loading="store.loading"
          :placeholder="senderPlaceholder"
          @submit="handleSend"
        />
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ── 整体布局 ── */
.chat-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #f0f2f5;
}

/* ── 左侧侧边栏 ── */
.sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid #f0f0f0;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 12px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.logo-title {
  font-size: 15px;
  font-weight: 600;
  color: #1677ff;
  letter-spacing: 0.5px;
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.empty-tip {
  text-align: center;
  color: #bfbfbf;
  font-size: 13px;
  padding: 32px 16px;
}

/* ── 右侧聊天面板 ── */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bubble-row {
  display: flex;
  flex-direction: column;
}

/* 欢迎提示 */
.welcome-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: #8c8c8c;
}

.welcome-icon {
  font-size: 48px;
  color: #1677ff;
}

/* ── 底部输入区 ── */
.input-area {
  padding: 0 32px 20px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.analysis-summary { width: min(760px, 100%); padding: 12px 0; }
.analysis-summary-header, .analysis-metrics { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.analysis-metrics { margin: 8px 0; color: #595959; font-size: 12px; }

.sender-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  min-height: 34px;
  color: #595959;
  font-size: 12px;
}

.cancel-bar {
  display: flex;
  justify-content: center;
  padding: 6px 0 2px;
}

.input-hitl-hint {
  padding: 8px 0 4px;
  font-size: 13px;
  color: #0958d9;
  border-bottom: 1px dashed #91caff;
  margin-bottom: 8px;
}
</style>
