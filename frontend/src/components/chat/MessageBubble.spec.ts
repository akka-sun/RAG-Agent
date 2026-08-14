import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Message } from '@/types/api'
import MessageBubble from './MessageBubble.vue'

const citation = {
  id: 'citation-1',
  document_id: 'document-1',
  chunk_id: 'chunk-1',
  source_label: 'S1',
  quote: '引用内容',
  page_number: 3,
  section: '概述',
  score: 0.92,
  metadata: { filename: '指南.pdf' },
}

function message(content: string, citations = [citation]): Message {
  return {
    id: 'message-1',
    conversation_id: 'conversation-1',
    role: 'assistant',
    content,
    status: 'completed',
    created_at: '2026-08-14T00:00:00Z',
    token_count: null,
    citations,
  }
}

describe('MessageBubble', () => {
  it('renders user and assistant messages with distinct accessible labels', () => {
    const assistant = mount(MessageBubble, { props: { message: message('回答') } })
    const user = mount(MessageBubble, {
      props: { message: { ...message('问题', []), role: 'user' } },
    })

    expect(assistant.get('article').attributes('aria-label')).toBe('助手消息')
    expect(assistant.get('article').classes()).toContain('message-bubble--assistant')
    expect(user.get('article').attributes('aria-label')).toBe('你的消息')
    expect(user.get('article').classes()).toContain('message-bubble--user')
  })

  it('tokenizes multiple and repeated matching citations while leaving unknown labels as text', async () => {
    const secondCitation = { ...citation, id: 'citation-2', source_label: 'S2', chunk_id: 'chunk-2' }
    const wrapper = mount(MessageBubble, {
      props: { message: message('第一处 [S1]，第二处 [S2]，再次 [S1]，未知 [S9]。', [citation, secondCitation]) },
    })

    const buttons = wrapper.findAll('button')
    expect(buttons.map((button) => button.text())).toEqual(['[S1]', '[S2]', '[S1]'])
    expect(buttons[0].attributes('aria-label')).toBe('查看引用 S1')
    expect(wrapper.text()).toContain('未知 [S9]。')

    await buttons[1].trigger('click')
    expect(wrapper.emitted('citation')?.[0]).toEqual([secondCitation])
  })
})
