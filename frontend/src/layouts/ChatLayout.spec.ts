import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ChatLayout from './ChatLayout.vue'

function media(matches: boolean) {
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
    matches,
    media: '(max-width: 64rem)',
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
}

describe('ChatLayout', () => {
  beforeEach(() => media(true))
  afterEach(() => {
    document.body.replaceChildren()
    vi.unstubAllGlobals()
  })

  it('removes a closed responsive rail from interaction while leaving the desktop rail interactive', async () => {
    const overlay = mount(ChatLayout, { props: { railOpen: false }, slots: { rail: '<button>会话</button>' } })
    await overlay.vm.$nextTick()
    expect(overlay.get('#conversation-history').attributes('inert')).toBeDefined()
    expect(overlay.get('#conversation-history').attributes('aria-hidden')).toBe('true')

    media(false)
    const desktop = mount(ChatLayout, { props: { railOpen: false }, slots: { rail: '<button>会话</button>' } })
    await desktop.vm.$nextTick()
    expect(desktop.get('#conversation-history').attributes('inert')).toBeUndefined()
    expect(desktop.get('#conversation-history').attributes('aria-hidden')).toBeUndefined()
  })

  it('moves and traps focus in an open rail, closes with Escape, and restores its trigger', async () => {
    const trigger = document.createElement('button')
    trigger.textContent = '打开'
    document.body.append(trigger)
    trigger.focus()
    const wrapper = mount(ChatLayout, {
      attachTo: document.body,
      props: { railOpen: false },
      slots: { rail: '<button id="first-rail">第一项</button><button id="last-rail">最后一项</button>' },
    })

    await wrapper.setProps({ railOpen: true })
    await wrapper.vm.$nextTick()
    expect(document.activeElement).toBe(wrapper.get('#first-rail').element)
    expect(wrapper.get('.chat-layout__main').attributes('inert')).toBeDefined()

    ;(wrapper.get('#last-rail').element as HTMLElement).focus()
    await wrapper.get('#last-rail').trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(wrapper.get('#first-rail').element)
    await wrapper.get('#conversation-history').trigger('keydown', { key: 'Escape' })
    expect(wrapper.emitted('closeRail')).toHaveLength(1)
    await wrapper.setProps({ railOpen: false })
    await wrapper.vm.$nextTick()
    expect(document.activeElement).toBe(trigger)
  })
})
