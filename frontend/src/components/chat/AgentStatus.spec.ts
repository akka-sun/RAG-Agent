import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AgentStatus from './AgentStatus.vue'

describe('AgentStatus', () => {
  it.each([
    ['streaming', 'running', '助手正在生成回答'],
    ['retrieving', null, '正在检索知识库'],
    ['cancelled', null, '生成已停止'],
  ] as const)('renders %s without inventing tool activity', (phase, status, expected) => {
    const wrapper = mount(AgentStatus, { props: { phase, status, error: null } })
    expect(wrapper.text()).toContain(expected)
    expect(wrapper.text()).not.toContain('工具')
  })

  it('announces a concise backend failure', () => {
    const wrapper = mount(AgentStatus, { props: { phase: 'failed', status: null, error: '模型服务不可用' } })
    expect(wrapper.get('[role="alert"]').text()).toContain('模型服务不可用')
  })
})
