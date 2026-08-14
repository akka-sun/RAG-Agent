import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'
import ModalDialog from './ModalDialog.vue'

describe('ModalDialog', () => {
  afterEach(() => document.body.replaceChildren())

  it('isolates the background, traps focus, closes on Escape, and restores the opener focus', async () => {
    const background = document.createElement('main')
    const opener = document.createElement('button')
    background.append(opener)
    document.body.append(background)
    opener.focus()

    const wrapper = mount(ModalDialog, {
      attachTo: document.body,
      props: { open: true, ariaLabel: '测试对话框' },
      slots: {
        default: '<button id="first">第一个</button><button id="last">最后一个</button>',
      },
    })
    await nextTick()

    const first = wrapper.get<HTMLButtonElement>('#first')
    const last = wrapper.get<HTMLButtonElement>('#last')
    expect(background.hasAttribute('inert')).toBe(true)
    expect(document.activeElement).toBe(first.element)

    last.element.focus()
    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(first.element)

    first.element.focus()
    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last.element)

    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('close')).toHaveLength(1)
    await wrapper.setProps({ open: false })
    await nextTick()

    expect(background.hasAttribute('inert')).toBe(false)
    expect(document.activeElement).toBe(opener)
  })

  it('honors an explicit initial-focus target', async () => {
    const wrapper = mount(ModalDialog, {
      attachTo: document.body,
      props: { open: true, ariaLabelledby: 'modal-title', initialFocus: '#preferred' },
      slots: {
        default: '<h2 id="modal-title">标题</h2><button>默认</button><input id="preferred">',
      },
    })
    await nextTick()

    expect(document.activeElement).toBe(wrapper.get('#preferred').element)
  })
})
