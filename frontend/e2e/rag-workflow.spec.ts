import { ANSWER, CHUNK_ID, CONVERSATION_ID, DOCUMENT_ID, KB_ID, expect, test } from './fixtures'

async function expectNoPageOverflow(page: import('@playwright/test').Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(1)
}

async function openProductNavigation(page: import('@playwright/test').Page): Promise<void> {
  const toggle = page.getByRole('button', { name: '打开主导航' })
  if (await toggle.isVisible()) await toggle.click()
}

async function inspectConversationRail(page: import('@playwright/test').Page): Promise<void> {
  const toggle = page.getByRole('button', { name: '打开会话历史' })
  const rail = page.getByRole('complementary', { name: '会话历史' })
  if (await toggle.isVisible()) {
    await toggle.click()
    await expect(rail).toBeVisible()
    await page.getByRole('button', { name: '关闭会话历史' }).click()
  } else {
    await expect(rail).toBeVisible()
  }
}

test('completes the RAG workflow from an empty knowledge base to a persisted cited answer', async ({ page, mockApi }) => {
  await page.goto('/knowledge-bases')
  await expect(page.getByRole('heading', { name: '知识库', exact: true })).toBeVisible()
  await expect(page.getByText('还没有知识库')).toBeVisible()

  await page.getByLabel('知识库名称').fill('产品资料库')
  await page.getByLabel('嵌入模型').fill('text-embedding-3-small')
  await page.getByLabel('向量维度').fill('1536')
  await page.getByRole('button', { name: '创建知识库' }).click()
  await expect(page).toHaveURL(new RegExp(`/knowledge-bases/${KB_ID}$`))

  await page.getByLabel('选择文档').setInputFiles({
    name: 'sample.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 保修政策\n产品保修期为两年', 'utf8'),
  })
  await page.getByRole('button', { name: '上传文档' }).click()
  const ingestionProgress = page.getByRole('region', { name: '摄取任务' })
  await expect(ingestionProgress.getByText('处理中', { exact: true })).toBeVisible({ timeout: 7_000 })
  await expect(ingestionProgress.getByText('处理完成', { exact: true })).toBeVisible({ timeout: 12_000 })
  await expect(page.getByRole('cell', { name: 'sample.md' })).toBeVisible()
  await expectNoPageOverflow(page)

  await openProductNavigation(page)
  await page.getByRole('link', { name: '新对话' }).click()
  const createDialog = page.getByRole('dialog', { name: '创建会话' })
  await createDialog.getByLabel('会话标题').fill('保修政策咨询')
  await createDialog.getByRole('button', { name: '创建', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`conversation=${CONVERSATION_ID}`))
  await inspectConversationRail(page)

  await page.getByLabel('输入消息').fill('产品保修多久？')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByRole('log', { name: '消息记录' })).toContainText(ANSWER)
  expect(mockApi.state.messagesByConversation.get(CONVERSATION_ID)).toHaveLength(2)

  await page.getByRole('button', { name: '查看引用 S1' }).click()
  const citationDialog = page.getByRole('dialog', { name: '引用来源' })
  await expect(citationDialog).toContainText('产品保修期为两年')
  await expect(citationDialog).toContainText(DOCUMENT_ID)
  await expect(citationDialog).toContainText(CHUNK_ID)
  await expect(citationDialog).toContainText('sample.md')
  await expectNoPageOverflow(page)
})

test('offers a deterministic retry after a failed message stream', async ({ page, mockApi }) => {
  mockApi.seedCompleteWorkflow()
  mockApi.failNextStream()

  await page.goto(`/?conversation=${CONVERSATION_ID}`)
  await expect(page.getByRole('heading', { name: '保修政策咨询' })).toBeVisible()
  await page.getByLabel('输入消息').fill('产品保修多久？')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('生成失败：模拟流式失败')

  await page.getByRole('button', { name: '重试上一条消息' }).click()
  await expect(page.getByRole('log', { name: '消息记录' })).toContainText(ANSWER)
  expect(mockApi.state.streamAttempts).toBe(2)
  expect(mockApi.state.messagesByConversation.get(CONVERSATION_ID)).toHaveLength(2)
  await expectNoPageOverflow(page)
})

test('labels unsupported infrastructure and supports refreshed chat and knowledge-base deep links', async ({ page, mockApi }) => {
  mockApi.seedCompleteWorkflow()

  await page.goto('/status')
  await expect(page.getByRole('heading', { name: '系统状态' })).toBeVisible()
  await expect(page.getByText('后端未提供检测接口', { exact: true })).toHaveCount(4)
  await expectNoPageOverflow(page)

  const chatResponse = await page.goto('/chat')
  expect(chatResponse?.status()).toBe(200)
  await expect(page.getByRole('heading', { name: '新对话' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: '新对话' })).toBeVisible()

  const detailResponse = await page.goto(`/knowledge-bases/${KB_ID}`)
  expect(detailResponse?.status()).toBe(200)
  await expect(page.getByRole('heading', { name: '文档', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: '文档', exact: true })).toBeVisible()
  await expectNoPageOverflow(page)
})
