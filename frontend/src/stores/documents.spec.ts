import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useDocumentStore } from './documents'
import type { DocumentRecord, IngestionTask, TaskStatus } from '@/types/api'

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

const documentRecord: DocumentRecord = {
  id: 'document-id',
  knowledge_base_id: 'knowledge-base-id',
  filename: 'notes.txt',
  content_type: 'text/plain',
  size_bytes: 12,
  parser_name: 'local',
  source_object_key: 'source-key',
  parsed_object_key: 'parsed-key',
  status: 'completed',
  chunk_count: 2,
  error: null,
  created_at: '2026-08-14T00:00:00Z',
  updated_at: '2026-08-14T00:01:00Z',
}

function task(status: TaskStatus, progress = 0): IngestionTask {
  return {
    id: 'task-id',
    document_id: 'document-id',
    arq_job_id: 'job-id',
    status,
    stage: status === 'pending' ? 'queued' : 'parsing',
    progress,
    error: status === 'failed' ? '解析器不可用' : null,
    created_at: '2026-08-14T00:00:00Z',
    started_at: status === 'pending' ? null : '2026-08-14T00:00:01Z',
    completed_at: status === 'completed' || status === 'failed'
      ? '2026-08-14T00:00:06Z'
      : null,
  }
}

describe('document store polling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    setActivePinia(createPinia())
    api.upload.mockResolvedValue({
      document_id: 'document-id',
      task_id: 'task-id',
      status: 'pending',
    })
    api.list.mockResolvedValue([documentRecord])
  })

  it('keeps the accepted document and task IDs and polls after 1s, 2s, then 3s', async () => {
    api.task.mockResolvedValue(task('processing', 20))
    const store = useDocumentStore()

    await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))

    expect(store.tasks['task-id']).toMatchObject({
      taskId: 'task-id',
      documentId: 'document-id',
      knowledgeBaseId: 'knowledge-base-id',
    })
    await vi.advanceTimersByTimeAsync(999)
    expect(api.task).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1_999)
    expect(api.task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(2_999)
    expect(api.task).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(1)
    expect(api.task).toHaveBeenCalledTimes(3)

    store.stopAllPolling()
  })

  it.each(['completed', 'failed'] as const)(
    'stops on %s and refreshes that knowledge base exactly once',
    async (status) => {
      api.task.mockResolvedValue(task(status, 100))
      const store = useDocumentStore()
      await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))

      await vi.advanceTimersByTimeAsync(1_000)
      await vi.advanceTimersByTimeAsync(20_000)

      expect(api.task).toHaveBeenCalledTimes(1)
      expect(api.list).toHaveBeenCalledTimes(1)
      expect(api.list).toHaveBeenCalledWith('knowledge-base-id')
      expect(store.tasks['task-id'].task?.status).toBe(status)
    },
  )

  it('stops after five consecutive network failures and exposes a recovery action', async () => {
    api.task.mockRejectedValue(new TypeError('network down'))
    const store = useDocumentStore()
    await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))

    await vi.advanceTimersByTimeAsync(15_000)
    await vi.advanceTimersByTimeAsync(30_000)

    expect(api.task).toHaveBeenCalledTimes(5)
    expect(store.tasks['task-id'].pollingError).toBe('任务状态获取失败，请检查网络后刷新页面重试。')
  })

  it('clears scheduled work and aborts an in-flight request during teardown', async () => {
    let requestSignal: AbortSignal | undefined
    api.task.mockImplementation((_taskId: string, signal?: AbortSignal) => {
      requestSignal = signal
      return new Promise((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      })
    })
    const store = useDocumentStore()
    await store.upload('knowledge-base-id', new File(['notes'], 'notes.txt'))
    await vi.advanceTimersByTimeAsync(1_000)

    store.stopAllPolling()
    await vi.advanceTimersByTimeAsync(30_000)

    expect(requestSignal?.aborted).toBe(true)
    expect(api.task).toHaveBeenCalledTimes(1)
    expect(api.list).not.toHaveBeenCalled()
  })

  it('forwards a selected PDF parser to the multipart API boundary', async () => {
    const store = useDocumentStore()
    const file = new File(['pdf'], 'report.pdf', { type: 'application/pdf' })

    await store.upload('knowledge-base-id', file, 'mineru')

    expect(api.upload).toHaveBeenCalledWith('knowledge-base-id', file, 'mineru')
    store.stopAllPolling()
  })

  it('tracks a backend retry task and resumes polling it', async () => {
    api.retry.mockResolvedValue(task('pending'))
    api.task.mockResolvedValue(task('processing', 10))
    const store = useDocumentStore()

    await store.retry('knowledge-base-id', 'document-id')
    await vi.advanceTimersByTimeAsync(1_000)

    expect(store.tasks['task-id'].task?.status).toBe('processing')
    expect(api.task).toHaveBeenCalledWith('task-id', expect.any(AbortSignal))
    store.stopAllPolling()
  })

  it('deletes a document only after the API succeeds', async () => {
    api.delete.mockResolvedValue(undefined)
    const store = useDocumentStore()
    store.documentsByKnowledgeBase['knowledge-base-id'] = [documentRecord]

    await store.remove('knowledge-base-id', 'document-id')

    expect(api.delete).toHaveBeenCalledWith('knowledge-base-id', 'document-id')
    expect(store.documentsByKnowledgeBase['knowledge-base-id']).toEqual([])
  })
})
