import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '@/views/ChatView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/chat', component: ChatView },
    { path: '/chat/:threadId', component: ChatView },
  ],
})
