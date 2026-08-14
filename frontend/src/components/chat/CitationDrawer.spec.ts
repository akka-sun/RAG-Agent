import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'
import CitationDrawer from './CitationDrawer.vue'

const citation = {
  id: 'citation-1',
  document_id: 'document-1',
  chunk_id: 'chunk-1',
  source_label: 'S1',
  quote: '知识库用于保存团队资料。',
  page_number: 3,
  section: '产品概述',
  score: 0.9234,
  metadata: { filename: '产品指南.pdf' },
}

describe('CitationDrawer', () => {
  afterEach(() => document.body.replaceChildren())

  it('renders only provided citation fields without fabricating a source URL', async () => {
    const wrapper = mount(CitationDrawer, { attachTo: document.body, props: { open: true, citation } })
    await nextTick()

    expect(wrapper.get('[role="dialog"]').attributes('aria-modal')).toBe('true')
    expect(wrapper.text()).toContain('产品指南.pdf')
    expect(wrapper.text()).toContain('产品概述')
    expect(wrapper.text()).toContain('第 3 页')
    expect(wrapper.text()).toContain('92.3%')
    expect(wrapper.text()).toContain('知识库用于保存团队资料。')
    expect(wrapper.text()).toContain('document-1')
    expect(wrapper.text()).toContain('chunk-1')
    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('falls back to an unknown filename and closes with Escape while restoring focus', async () => {
    const trigger = document.createElement('button')
    document.body.append(trigger)
    trigger.focus()
    const wrapper = mount(CitationDrawer, {
      attachTo: document.body,
      props: { open: true, citation: { ...citation, metadata: {} } },
    })
    await nextTick()
    const close = wrapper.get('button[aria-label="关闭引用详情"]')
    expect(document.activeElement).toBe(close.element)
    expect(wrapper.text()).toContain('未知文件')

    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Escape' })
    await nextTick()
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(document.activeElement).toBe(trigger)
  })
})
