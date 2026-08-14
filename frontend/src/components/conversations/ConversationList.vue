<script setup lang="ts">
import type { Conversation, Message } from '@/types/api'

defineProps<{
  conversations: Conversation[]
  messagesByConversation: Record<string, Message[]>
}>()

defineEmits<{
  enter: [conversationId: string]
  remove: [conversationId: string]
}>()

function loaded(messagesByConversation: Record<string, Message[]>, conversationId: string): boolean {
  return Object.hasOwn(messagesByConversation, conversationId)
}
</script>

<template>
  <ul class="conversation-list" aria-label="会话列表">
    <li v-for="conversation in conversations" :key="conversation.id" class="conversation-list__item">
      <div>
        <h3>{{ conversation.title }}</h3>
        <p v-if="loaded(messagesByConversation, conversation.id)">{{ messagesByConversation[conversation.id].length }} 条消息</p>
      </div>
      <div class="conversation-list__actions">
        <button type="button" class="button button--secondary" @click="$emit('enter', conversation.id)">进入会话</button>
        <button type="button" class="button button--danger" @click="$emit('remove', conversation.id)">删除</button>
      </div>
    </li>
  </ul>
</template>

<style scoped>
.conversation-list { display: grid; gap: 0.75rem; margin: 0; padding: 0; list-style: none; }
.conversation-list__item { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem; border: 1px solid var(--color-border); border-radius: 0.75rem; }
.conversation-list__item h3, .conversation-list__item p { margin: 0; }
.conversation-list__item p { margin-top: 0.375rem; color: var(--color-text-muted); font-size: 0.875rem; }
.conversation-list__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.5rem; }
@media (max-width: 36rem) { .conversation-list__item { align-items: flex-start; flex-direction: column; } .conversation-list__actions { justify-content: flex-start; } }
</style>
