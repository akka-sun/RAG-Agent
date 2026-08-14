<script setup lang="ts">
import { computed, nextTick, onBeforeUpdate, onMounted, onUpdated, ref } from 'vue'
import type { CitationData } from '@/api/sse'
import type { ChatPhase, OptimisticUserMessage } from '@/stores/chat'
import type { Message, MessageCitation } from '@/types/api'
import MessageBubble, { type DisplayMessage } from './MessageBubble.vue'

const props = defineProps<{
  conversationId: string
  messages: Message[]
  optimisticUser: OptimisticUserMessage | null
  draftAssistant: string
  draftCitations: CitationData[]
  phase: ChatPhase
}>()
defineEmits<{ citation: [citation: MessageCitation | CitationData] }>()

const scrollContainer = ref<HTMLElement | null>(null)
let shouldAutoScroll = true

const displayedMessages = computed<DisplayMessage[]>(() => {
  const result: DisplayMessage[] = [...props.messages]
  const optimistic = props.optimisticUser?.conversationId === props.conversationId
    ? props.optimisticUser
    : null

  if (optimistic) {
    result.push({ id: 'optimistic-user', role: 'user', content: optimistic.content, citations: [] })
  }

  if (props.draftAssistant) {
    const lastPersistedAssistant = [...props.messages].reverse().find((message) => message.role === 'assistant')
    const refreshedDraft = props.phase === 'completed'
      && !optimistic
      && lastPersistedAssistant?.content === props.draftAssistant
    if (!refreshedDraft) {
      result.push({
        id: 'draft-assistant',
        role: 'assistant',
        content: props.draftAssistant,
        citations: props.draftCitations,
      })
    }
  }

  return result
})

function nearBottom(element: HTMLElement): boolean {
  return element.scrollHeight - element.scrollTop - element.clientHeight < 96
}

function scrollToBottom(): void {
  const element = scrollContainer.value
  if (element) element.scrollTop = element.scrollHeight
}

onBeforeUpdate(() => {
  shouldAutoScroll = scrollContainer.value ? nearBottom(scrollContainer.value) : true
})
onUpdated(async () => {
  if (!shouldAutoScroll) return
  await nextTick()
  scrollToBottom()
})
onMounted(async () => {
  await nextTick()
  scrollToBottom()
})
</script>

<template>
  <div
    ref="scrollContainer"
    class="message-list"
    role="log"
    aria-label="消息记录"
    aria-live="polite"
  >
    <p v-if="displayedMessages.length === 0" class="message-list__empty">还没有消息，输入问题开始对话。</p>
    <MessageBubble
      v-for="message in displayedMessages"
      :key="message.id"
      :message="message"
      @citation="$emit('citation', $event)"
    />
  </div>
</template>

<style scoped>
.message-list {
  display: grid;
  align-content: start;
  gap: 0.875rem;
  min-height: 0;
  padding: 1.25rem max(1rem, calc((100% - 48rem) / 2));
  overflow-y: auto;
  overscroll-behavior: contain;
}

.message-list__empty {
  align-self: center;
  justify-self: center;
  margin: 3rem 0;
  color: var(--color-text-muted);
  text-align: center;
}
</style>
