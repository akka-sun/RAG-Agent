import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatComposer from './ChatComposer.vue'

describe('ChatComposer', () => {
  it('submits trimmed content with Enter and keeps Shift+Enter as a newline', async () => {
    const wrapper = mount(ChatComposer)
    const textarea = wrapper.get('textarea')
    await textarea.setValue('  怎么部署？  ')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(wrapper.emitted('submit')).toBeUndefined()

    await textarea.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('submit')?.[0]).toEqual(['怎么部署？'])
    expect((textarea.element as HTMLTextAreaElement).value).toBe('')
  })

  it('blocks whitespace-only input and disables sending during an active stream', async () => {
    const wrapper = mount(ChatComposer)
    await wrapper.get('textarea').setValue('   ')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')).toBeUndefined()

    await wrapper.setProps({ active: true })
    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button[aria-label="停止生成"]').exists()).toBe(true)
    expect(wrapper.find('button[aria-label="重试上一条消息"]').exists()).toBe(false)
  })

  it('emits cancel only while active and retry only for a retryable message', async () => {
    const wrapper = mount(ChatComposer, { props: { active: true, canRetry: true } })
    await wrapper.get('button[aria-label="停止生成"]').trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)

    await wrapper.setProps({ active: false })
    await wrapper.get('button[aria-label="重试上一条消息"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})
