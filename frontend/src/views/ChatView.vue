<script setup lang="ts">
import { h, ref, nextTick, onMounted } from 'vue'
import { Bubble, Conversations, Sender } from 'ant-design-x-vue'
import type { ConversationsProps } from 'ant-design-x-vue'
import { PlusOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons-vue'
import { useChatStore } from '@/stores/chat'

const store = useChatStore()
const inputValue = ref('')
const messagesEndRef = ref<HTMLDivElement | null>(null)

onMounted(() => {
  store.loadHistory()
})

// 自动滚动到最新消息
async function scrollToBottom() {
  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
}

async function handleSend(val: string) {
  if (!val.trim() || store.loading) return
  inputValue.value = ''
  await store.sendMessage(val)
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
      <!-- 上半部分：消息列表 -->
      <div class="messages-area">
        <div v-if="store.messages.length === 0" class="welcome-hint">
          <RobotOutlined class="welcome-icon" />
          <p>你好！我是 ERP 智能助手，请输入您的问题开始对话。</p>
        </div>

        <template v-else>
          <div
            v-for="msg in store.messages"
            :key="msg.id"
            class="bubble-row"
            :class="msg.role"
          >
            <Bubble
              :content="msg.content"
              :placement="msg.role === 'user' ? 'end' : 'start'"
              :loading="msg.loading"
              :avatar="
                msg.role === 'user'
                  ? { icon: h(UserOutlined) }
                  : { icon: h(RobotOutlined), style: { background: '#1677ff' } }
              "
            />
          </div>
        </template>

        <div ref="messagesEndRef" />
      </div>

      <!-- 下半部分：输入框 -->
      <div class="input-area">
        <Sender
          v-model:value="inputValue"
          :loading="store.loading"
          placeholder="输入消息，按 Enter 发送…"
          @submit="handleSend"
        />
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ── 整体布局：左侧边栏 + 右侧聊天面板 ── */
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

/* 上半：消息区域 */
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

/* 下半：输入区 */
.input-area {
  padding: 16px 32px 20px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
  flex-shrink: 0;
}
</style>
