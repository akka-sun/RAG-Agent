import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import AppSidebar from './AppSidebar.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/', component: { template: '<div />' } }],
})

describe('AppSidebar', () => {
  it('renders all implemented product areas', () => {
    const wrapper = mount(AppSidebar, { global: { plugins: [router] } })

    expect(wrapper.text()).toContain('新对话')
    expect(wrapper.text()).toContain('会话')
    expect(wrapper.text()).toContain('知识库')
    expect(wrapper.text()).toContain('文档')
    expect(wrapper.text()).toContain('系统状态')
  })
})
