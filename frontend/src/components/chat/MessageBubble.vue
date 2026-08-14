<script setup lang="ts">
import { computed } from 'vue'
import type { CitationData } from '@/api/sse'
import type { Message, MessageCitation } from '@/types/api'

export interface DisplayMessage extends Pick<Message, 'id' | 'role' | 'content'> {
  citations: Array<MessageCitation | CitationData>
}

const props = defineProps<{ message: DisplayMessage }>()
defineEmits<{ citation: [citation: MessageCitation | CitationData] }>()

interface MessageSegment {
  text: string
  citation?: MessageCitation | CitationData
}

function citationToken(citation: MessageCitation | CitationData): string {
  return citation.source_label.startsWith('[') ? citation.source_label : `[${citation.source_label}]`
}

const segments = computed<MessageSegment[]>(() => {
  const citationsByToken = new Map(props.message.citations.map((citation) => [citationToken(citation), citation]))
  const result: MessageSegment[] = []
  const pattern = /\[S\d+\]/g
  let cursor = 0

  for (const match of props.message.content.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > cursor) result.push({ text: props.message.content.slice(cursor, index) })
    const citation = citationsByToken.get(match[0])
    result.push(citation ? { text: match[0], citation } : { text: match[0] })
    cursor = index + match[0].length
  }

  if (cursor < props.message.content.length) result.push({ text: props.message.content.slice(cursor) })
  return result.length ? result : [{ text: props.message.content }]
})
</script>

<template>
  <article
    class="message-bubble"
    :class="`message-bubble--${message.role === 'user' ? 'user' : 'assistant'}`"
    :aria-label="message.role === 'user' ? '你的消息' : '助手消息'"
  >
    <p class="message-bubble__role">{{ message.role === 'user' ? '你' : '助手' }}</p>
    <p class="message-bubble__content">
      <template v-for="(segment, index) in segments" :key="index">
        <button
          v-if="segment.citation"
          type="button"
          class="message-bubble__citation"
          :aria-label="`查看引用 ${segment.citation.source_label}`"
          @click="$emit('citation', segment.citation)"
        >{{ segment.text }}</button>
        <template v-else>{{ segment.text }}</template>
      </template>
    </p>
  </article>
</template>

<style scoped>
.message-bubble {
  display: grid;
  gap: 0.375rem;
  width: fit-content;
  max-width: min(46rem, 88%);
  padding: 0.875rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 1rem 1rem 1rem 0.25rem;
  background: var(--color-surface);
}

.message-bubble--user {
  justify-self: end;
  border-color: transparent;
  border-radius: 1rem 1rem 0.25rem;
  color: #fff;
  background: var(--color-action);
}

.message-bubble__role,
.message-bubble__content {
  margin: 0;
}

.message-bubble__role {
  color: var(--color-text-muted);
  font-size: 0.75rem;
  font-weight: 700;
}

.message-bubble--user .message-bubble__role {
  color: rgb(255 255 255 / 78%);
}

.message-bubble__content {
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.message-bubble__citation {
  display: inline;
  margin: 0 0.125rem;
  padding: 0.0625rem 0.25rem;
  border: 0;
  border-radius: 0.25rem;
  color: var(--color-action);
  background: #eef0ff;
  font-size: 0.8125em;
  font-weight: 700;
  vertical-align: baseline;
}
</style>
