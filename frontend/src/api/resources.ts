import { apiBlob, apiJson, type ApiRequestInit, type BlobResponse } from './client'
import type { Conversation, DocumentAccepted, DocumentRecord, HealthResponse, IngestionTask, KnowledgeBase, KnowledgeBaseCreate, Message } from '@/types/api'

const apiPath = (path: string) => `/api/v1${path}`
const segment = (value: string) => encodeURIComponent(value)
const request = (signal?: AbortSignal): Pick<ApiRequestInit, 'signal'> => ({ signal })

export const knowledgeBasesApi = {
  create: (data: KnowledgeBaseCreate, signal?: AbortSignal) => apiJson<KnowledgeBase>(apiPath('/knowledge-bases'), { method: 'POST', body: data, ...request(signal) }),
  list: (signal?: AbortSignal) => apiJson<KnowledgeBase[]>(apiPath('/knowledge-bases'), request(signal)),
  get: (knowledgeBaseId: string, signal?: AbortSignal) => apiJson<KnowledgeBase>(apiPath(`/knowledge-bases/${segment(knowledgeBaseId)}`), request(signal)),
  delete: (knowledgeBaseId: string, signal?: AbortSignal) => apiJson<void>(apiPath(`/knowledge-bases/${segment(knowledgeBaseId)}`), { method: 'DELETE', ...request(signal) }),
}

export const documentsApi = {
  list: (knowledgeBaseId: string, signal?: AbortSignal) => apiJson<DocumentRecord[]>(documentsPath(knowledgeBaseId), request(signal)),
  upload: (knowledgeBaseId: string, file: File, parser?: string, signal?: AbortSignal) => {
    const body = new FormData()
    body.set('file', file)
    if (parser !== undefined) body.set('parser', parser)
    return apiJson<DocumentAccepted>(documentsPath(knowledgeBaseId), { method: 'POST', body, ...request(signal) })
  },
  get: (knowledgeBaseId: string, documentId: string, signal?: AbortSignal) => apiJson<DocumentRecord>(documentPath(knowledgeBaseId, documentId), request(signal)),
  source: (knowledgeBaseId: string, documentId: string, signal?: AbortSignal): Promise<BlobResponse> => apiBlob(`${documentPath(knowledgeBaseId, documentId)}/source`, request(signal)),
  parsed: (knowledgeBaseId: string, documentId: string, signal?: AbortSignal): Promise<BlobResponse> => apiBlob(`${documentPath(knowledgeBaseId, documentId)}/parsed`, request(signal)),
  image: (knowledgeBaseId: string, documentId: string, assetIndex: number, signal?: AbortSignal): Promise<BlobResponse> => apiBlob(`${documentPath(knowledgeBaseId, documentId)}/images/${assetIndex}`, request(signal)),
  retry: (knowledgeBaseId: string, documentId: string, signal?: AbortSignal) => apiJson<IngestionTask>(`${documentPath(knowledgeBaseId, documentId)}/retry`, { method: 'POST', ...request(signal) }),
  delete: (knowledgeBaseId: string, documentId: string, signal?: AbortSignal) => apiJson<void>(documentPath(knowledgeBaseId, documentId), { method: 'DELETE', ...request(signal) }),
  task: (taskId: string, signal?: AbortSignal) => apiJson<IngestionTask>(apiPath(`/ingestion-tasks/${segment(taskId)}`), request(signal)),
}

export const conversationsApi = {
  list: (knowledgeBaseId: string, signal?: AbortSignal) => apiJson<Conversation[]>(conversationsPath(knowledgeBaseId), request(signal)),
  create: (knowledgeBaseId: string, data: { title: string }, signal?: AbortSignal) => apiJson<Conversation>(conversationsPath(knowledgeBaseId), { method: 'POST', body: data, ...request(signal) }),
  get: (conversationId: string, signal?: AbortSignal) => apiJson<Conversation>(conversationPath(conversationId), request(signal)),
  delete: (conversationId: string, signal?: AbortSignal) => apiJson<void>(conversationPath(conversationId), { method: 'DELETE', ...request(signal) }),
  messages: (conversationId: string, signal?: AbortSignal) => apiJson<Message[]>(`${conversationPath(conversationId)}/messages`, request(signal)),
}

export const healthApi = { live: (signal?: AbortSignal) => apiJson<HealthResponse>(apiPath('/health/live'), request(signal)) }

function documentsPath(knowledgeBaseId: string): string { return apiPath(`/knowledge-bases/${segment(knowledgeBaseId)}/documents`) }
function documentPath(knowledgeBaseId: string, documentId: string): string { return `${documentsPath(knowledgeBaseId)}/${segment(documentId)}` }
function conversationsPath(knowledgeBaseId: string): string { return apiPath(`/knowledge-bases/${segment(knowledgeBaseId)}/conversations`) }
function conversationPath(conversationId: string): string { return apiPath(`/conversations/${segment(conversationId)}`) }
