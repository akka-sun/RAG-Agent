import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DocumentUploader, { validateUpload } from './DocumentUploader.vue'
import DocumentPreview from './DocumentPreview.vue'
import DocumentTable from './DocumentTable.vue'
import IngestionProgress from './IngestionProgress.vue'
import KnowledgeBaseDetailPage from '@/pages/KnowledgeBaseDetailPage.vue'
import { useDocumentStore } from '@/stores/documents'
import type { DocumentRecord, IngestionTask } from '@/types/api'

const api = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
  get: vi.fn(),
  source: vi.fn(),
  parsed: vi.fn(),
  image: vi.fn(),
  retry: vi.fn(),
  delete: vi.fn(),
  task: vi.fn(),
}))

vi.mock('@/api/resources', () => ({ documentsApi: api }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { knowledgeBaseId: 'knowledge-base-id' } }),
}))

const documentRecord: DocumentRecord = {
  id: 'document-id',
  knowledge_base_id: 'knowledge-base-id',
  filename: 'report.pdf',
  content_type: 'application/pdf',
  size_bytes: 100,
  parser_name: 'mineru',
  source_object_key: 'source-key',
  parsed_object_key: 'parsed-key',
  status: 'completed',
  chunk_count: 3,
  error: null,
  created_at: '2026-08-14T00:00:00Z',
  updated_at: '2026-08-14T00:01:00Z',
}

function chooseFile(wrapper: ReturnType<typeof mount>, file: File) {
  const input = wrapper.get<HTMLInputElement>('input[type="file"]')
  Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
  return input.trigger('change')
}

describe('upload validation', () => {
  it('rejects empty, oversized, and unsupported files with the required messages', () => {
    expect(validateUpload(new File([], 'empty.md'))).toBe('文件不能为空')
    expect(validateUpload(new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.pdf')))
      .toBe('文件不能超过 5 MiB')
    expect(validateUpload(new File(['x'], 'notes.docx'))).toBe('仅支持 .md、.txt 和 .pdf')
    expect(validateUpload(new File([new Uint8Array(5 * 1024 * 1024)], 'exact.pdf'))).toBeNull()
  })

  it('requires an explicit MinerU or PaddleX selection for PDF uploads', async () => {
    const wrapper = mount(DocumentUploader)
    const file = new File(['pdf'], 'report.pdf', { type: 'application/pdf' })
    await chooseFile(wrapper, file)

    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('请选择 PDF 解析器')
    expect(wrapper.emitted('upload')).toBeUndefined()

    await wrapper.get('select[name="parser"]').setValue('paddlex')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('upload')).toEqual([[file, 'paddlex']])
  })

  it('uploads text without fabricating a PDF parser', async () => {
    const wrapper = mount(DocumentUploader)
    const file = new File(['notes'], 'notes.md', { type: 'text/markdown' })
    await chooseFile(wrapper, file)

    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('upload')).toEqual([[file, undefined]])
    expect(wrapper.find('select[name="parser"]').exists()).toBe(false)
  })
})

describe('document preview resource safety', () => {
  const createObjectURL = vi.fn()
  const revokeObjectURL = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    createObjectURL.mockReturnValueOnce('blob:preview').mockReturnValue('blob:asset')
    const NativeURL = URL
    vi.stubGlobal('URL', class extends NativeURL {
      static createObjectURL = createObjectURL
      static revokeObjectURL = revokeObjectURL
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('revokes a PDF object URL when the preview unmounts', async () => {
    api.source.mockResolvedValue({
      blob: new Blob(['pdf'], { type: 'application/pdf' }),
      contentType: 'application/pdf',
      contentDisposition: 'attachment; filename="report.pdf"',
      filename: 'report.pdf',
      status: 200,
    })
    const wrapper = mount(DocumentPreview, {
      props: { knowledgeBaseId: 'knowledge-base-id', document: documentRecord },
    })

    await wrapper.get('button[name="preview-source"]').trigger('click')
    await flushPromises()
    wrapper.unmount()

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:preview')
  })

  it('renders parsed text as escaped text and only offers supplied asset indexes', async () => {
    api.parsed.mockResolvedValue({
      blob: new Blob([JSON.stringify({
        markdown: '<img src=x onerror=alert(1)>',
        assets: [{ asset_index: 3, mime_type: 'image/png', source_path: 'chart.png' }],
      })], { type: 'application/json' }),
      contentType: 'application/json',
      contentDisposition: null,
      filename: null,
      status: 200,
    })
    const wrapper = mount(DocumentPreview, {
      props: { knowledgeBaseId: 'knowledge-base-id', document: documentRecord },
    })

    await wrapper.get('button[name="preview-parsed"]').trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(wrapper.find('pre').exists()).toBe(true))

    expect(wrapper.get('pre').text()).toBe('<img src=x onerror=alert(1)>')
    expect(wrapper.find('pre img').exists()).toBe(false)
    expect(wrapper.text()).toContain('图片 3')
    expect(wrapper.text()).not.toContain('图片 0')
    expect(api.image).not.toHaveBeenCalled()
  })
})

describe('document management presentation', () => {
  it('shows only the specified document fields and confirms deletion', async () => {
    const failedDocument: DocumentRecord = {
      ...documentRecord,
      status: 'failed',
      error: '解析器不可用',
    }
    const wrapper = mount(DocumentTable, { props: { documents: [failedDocument] } })

    expect(wrapper.text()).toContain('report.pdf')
    expect(wrapper.text()).toContain('mineru')
    expect(wrapper.text()).toContain('100 B')
    expect(wrapper.text()).toContain('failed')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('解析器不可用')
    expect(wrapper.text()).not.toContain('source-key')
    expect(wrapper.text()).not.toContain('parsed-key')

    await wrapper.get('button[name="remove-document"]').trigger('click')
    expect(wrapper.emitted('remove')).toBeUndefined()
    expect(wrapper.text()).toContain('确认删除 report.pdf')
    await wrapper.get('button[name="confirm-remove-document"]').trigger('click')
    expect(wrapper.emitted('remove')).toEqual([['document-id']])

    await wrapper.get('button[name="retry-document"]').trigger('click')
    expect(wrapper.emitted('retry')).toEqual([['document-id']])
  })

  it('shows only known task progress plus an actionable polling error', () => {
    const ingestionTask: IngestionTask = {
      id: 'task-id',
      document_id: 'document-id',
      arq_job_id: 'job-id',
      status: 'processing',
      stage: 'parsing',
      progress: 42,
      error: null,
      created_at: '2026-08-14T00:00:00Z',
      started_at: '2026-08-14T00:00:01Z',
      completed_at: null,
    }
    const wrapper = mount(IngestionProgress, {
      props: {
        tasks: [{
          taskId: 'task-id',
          documentId: 'document-id',
          knowledgeBaseId: 'knowledge-base-id',
          task: ingestionTask,
          pollingError: '任务状态获取失败，请检查网络后刷新页面重试。',
        }],
      },
    })

    expect(wrapper.text()).toContain('processing')
    expect(wrapper.text()).toContain('parsing')
    expect(wrapper.text()).toContain('42%')
    expect(wrapper.text()).toContain('任务状态获取失败，请检查网络后刷新页面重试。')
  })
})

describe('knowledge-base document workspace', () => {
  it('loads the routed knowledge base and stops polling when the page unmounts', async () => {
    api.list.mockResolvedValue([documentRecord])
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDocumentStore()
    const stop = vi.spyOn(store, 'stopAllPolling')

    const wrapper = mount(KnowledgeBaseDetailPage, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(api.list).toHaveBeenCalledWith('knowledge-base-id')
    expect(wrapper.text()).toContain('report.pdf')
    expect(wrapper.findComponent(DocumentUploader).exists()).toBe(true)

    wrapper.unmount()
    expect(stop).toHaveBeenCalledTimes(1)
  })
})
