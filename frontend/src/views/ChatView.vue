<script setup lang="ts">
import { h, ref, computed, nextTick, onMounted } from 'vue'
import { Modal, message } from 'ant-design-vue'
import { Conversations, Sender } from 'ant-design-x-vue'
import type { ConversationsProps } from 'ant-design-x-vue'
import { PlusOutlined, RobotOutlined, StopOutlined, ToolOutlined } from '@ant-design/icons-vue'
import { useChatStore } from '@/stores/chat'
import MessageBubble from '@/components/MessageBubble.vue'
import HitlApprovalBar from '@/components/HitlApprovalBar.vue'

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
  store.loadSessions()
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

  let request: Promise<void>
  if (isInputHitl.value) {
    request = store.resumeInput(val.trim())
  } else {
    request = store.sendMessage(val.trim())
  }
  await scrollToBottom()
  await request
  scrollToBottom()
}

function confirmDeleteSession(threadId: string) {
  if (store.loading && store.currentThreadId === threadId) return

  Modal.confirm({
    title: '删除会话',
    content: '删除后无法恢复，是否继续？',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    async onOk() {
      try {
        await store.deleteSession(threadId)
      } catch {
        message.error('删除会话失败，请稍后重试')
      }
    },
  })
}

const sessionMenuConfig: ConversationsProps['menu'] = (session) => ({
  items: [{ key: 'delete', label: '删除', danger: true }],
  onClick: ({ key }) => {
    if (key === 'delete') confirmDeleteSession(session.key)
  },
})
</script>

<template>
  <div class="chat-layout">
    <!-- 左侧：会话历史侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="logo-title">Motorparts Agent</span>
        <a-button type="text" :icon="h(PlusOutlined)" @click="store.newSession" title="新建对话" />
      </div>

      <div class="sidebar-body">
        <Conversations
          :items="store.sessions"
          :active-key="store.currentThreadId ?? undefined"
          :menu="sessionMenuConfig"
          @activeChange="(key: string) => store.selectSession(key)"
        />
        <div v-if="store.sessions.length === 0" class="empty-tip">
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
          <p>你好！我是 Motorparts 智能助手，请输入您的问题开始对话。</p>
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
