import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import AppShell from './AppShell.vue'

vi.mock('@/api/resources', () => ({ knowledgeBasesApi: { list: vi.fn().mockResolvedValue([]) } }))

describe('AppShell', () => {
  it('provides an accessible narrow-screen navigation overlay control', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(AppShell, { global: { plugins: [createPinia(), router] } })
    const toggle = wrapper.get('button[aria-controls="global-navigation"]')
    expect(toggle.attributes('aria-expanded')).toBe('false')

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('#global-navigation').classes()).toContain('app-sidebar--open')
    expect(wrapper.find('.app-shell__nav-backdrop').exists()).toBe(true)
  })
})
