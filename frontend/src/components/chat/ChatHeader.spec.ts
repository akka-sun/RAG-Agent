import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatHeader from './ChatHeader.vue'

describe('ChatHeader', () => {
  it('connects the conversation rail toggle to its controlled overlay state', async () => {
    const wrapper = mount(ChatHeader, {
      props: { title: '会话', knowledgeBases: [], selectedKnowledgeBaseId: null, railOpen: false },
    })
    const toggle = wrapper.get('button[aria-controls="conversation-history"]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    await wrapper.setProps({ railOpen: true })
    expect(toggle.attributes('aria-expanded')).toBe('true')
  })
})
