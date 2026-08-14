import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AppShell from './AppShell.vue'

vi.mock('@/api/resources', () => ({ knowledgeBasesApi: { list: vi.fn().mockResolvedValue([]) } }))

describe('AppShell', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
      matches: true,
      media: '(max-width: 44rem)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  })
  afterEach(() => {
    document.body.replaceChildren()
    vi.unstubAllGlobals()
  })

  it('provides an accessible narrow-screen navigation overlay control', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(AppShell, {
      attachTo: document.body,
      global: {
        plugins: [createPinia(), router],
        stubs: { RouterLink: { template: '<a href="#"><slot /></a>' } },
      },
    })
    await wrapper.vm.$nextTick()
    const toggle = wrapper.get('button[aria-controls="global-navigation"]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('#global-navigation').attributes('inert')).toBeDefined()
    ;(toggle.element as HTMLElement).focus()

    await toggle.trigger('click')
    await wrapper.vm.$nextTick()
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('#global-navigation').classes()).toContain('app-sidebar--open')
    expect(wrapper.find('.app-shell__nav-backdrop').exists()).toBe(true)
    expect(wrapper.get('.app-shell__content').attributes('inert')).toBeDefined()
    expect(document.activeElement).toBe(wrapper.get('#global-navigation a').element)

    const links = wrapper.findAll('#global-navigation a')
    ;(links.at(-1)?.element as HTMLElement | undefined)?.focus()
    await links.at(-1)?.trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(links[0].element)

    await wrapper.get('#global-navigation').trigger('keydown', { key: 'Escape' })
    await wrapper.vm.$nextTick()
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(toggle.element)
  })

  it('keeps desktop navigation interactive when the overlay breakpoint is inactive', async () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
      matches: false,
      media: '(max-width: 44rem)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(AppShell, { global: { plugins: [createPinia(), router] } })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('#global-navigation').attributes('inert')).toBeUndefined()
    expect(wrapper.get('#global-navigation').attributes('aria-hidden')).toBeUndefined()
  })
})
