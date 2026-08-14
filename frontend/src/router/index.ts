import { createRouter, createWebHistory } from 'vue-router'
import ChatPage from '@/pages/ChatPage.vue'
import ConversationsPage from '@/pages/ConversationsPage.vue'
import KnowledgeBaseDetailPage from '@/pages/KnowledgeBaseDetailPage.vue'
import KnowledgeBasesPage from '@/pages/KnowledgeBasesPage.vue'
import StatusPage from '@/pages/StatusPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: ChatPage },
    { path: '/knowledge-bases', name: 'knowledge-bases', component: KnowledgeBasesPage },
    {
      path: '/knowledge-bases/:knowledgeBaseId',
      name: 'knowledge-base-detail',
      component: KnowledgeBaseDetailPage,
    },
    { path: '/conversations', name: 'conversations', component: ConversationsPage },
    { path: '/status', name: 'status', component: StatusPage },
  ],
})

export default router
