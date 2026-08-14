import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Message } from '@/types/api'
import MessageList from './MessageList.vue'

const conversationId = 'conversation-1'
const persisted: Message[] = [
  {
    id: 'user-1', conversation_id: conversationId, role: 'user', content: '怎么部署？', status: 'completed',
    created_at: '2026-08-14T00:00:00Z', token_count: null, citations: [],
  },
  {
    id: 'assistant-1', conversation_id: conversationId, role: 'assistant', content: '使用容器部署。', status: 'completed',
    created_at: '2026-08-14T00:00:01Z', token_count: null, citations: [],
  },
]

describe('MessageList', () => {
  it('does not treat an older identical Q/A pair as authoritative for the current turn', async () => {
    const wrapper = mount(MessageList, {
      props: {
        conversationId,
        messages: persisted,
        optimisticUser: { conversationId, content: '怎么部署？' },
        draftAssistant: '使用容器部署。',
        draftCitations: [],
        phase: 'completed',
        submissionBaselineMessageIds: persisted.map((message) => message.id),
      },
    })

    expect(wrapper.findAll('[aria-label="你的消息"]')).toHaveLength(2)
    expect(wrapper.findAll('[aria-label="助手消息"]')).toHaveLength(2)

    await wrapper.setProps({
      messages: [
        ...persisted,
        { ...persisted[0], id: 'user-2', created_at: '2026-08-14T00:00:02Z' },
        { ...persisted[1], id: 'assistant-2', created_at: '2026-08-14T00:00:03Z' },
      ],
    })
    expect(wrapper.findAll('[aria-label="你的消息"]')).toHaveLength(2)
    expect(wrapper.findAll('[aria-label="助手消息"]')).toHaveLength(2)
  })

  it('keeps the current optimistic user and partial assistant visible while streaming', () => {
    const wrapper = mount(MessageList, {
      props: {
        conversationId,
        messages: [],
        optimisticUser: { conversationId, content: '怎么部署？' },
        draftAssistant: '正在检索',
        draftCitations: [],
        phase: 'streaming',
      },
    })

    expect(wrapper.text()).toContain('怎么部署？')
    expect(wrapper.text()).toContain('正在检索')
  })

  it('ignores optimistic content belonging to another conversation', () => {
    const wrapper = mount(MessageList, {
      props: {
        conversationId,
        messages: persisted,
        optimisticUser: { conversationId: 'conversation-2', content: '不应出现' },
        draftAssistant: '',
        draftCitations: [],
        phase: 'idle',
      },
    })

    expect(wrapper.text()).not.toContain('不应出现')
  })
})
