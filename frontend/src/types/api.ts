export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  embedding_model: string
  embedding_dimension: number
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseCreate {
  name: string
  description: string
}

export interface DocumentRecord {
  id: string
  knowledge_base_id: string
  filename: string
  content_type: string
  size_bytes: number
  parser_name: string
  source_object_key: string
  parsed_object_key: string | null
  status: string
  chunk_count: number
  error: string | null
  created_at: string
  updated_at: string
}

export interface DocumentAccepted {
  document_id: string
  task_id: string
  status: 'pending'
}

export interface IngestionTask {
  id: string
  document_id: string
  arq_job_id: string | null
  status: TaskStatus
  stage: string
  progress: number
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface Conversation {
  id: string
  knowledge_base_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface MessageCitation {
  id: string
  document_id: string
  chunk_id: string
  source_label: string
  quote: string
  page_number: number | null
  section: string | null
  score: number | null
  metadata: Record<string, unknown>
}

export interface Message {
  id: string
  conversation_id: string
  role: string
  content: string
  status: string
  created_at: string
  token_count: number | null
  citations: MessageCitation[]
}

export interface HealthResponse {
  status: 'ok'
}

export type InfrastructureServiceName = 'postgresql' | 'redis' | 'minio' | 'milvus'

export interface ServiceReadiness {
  status: 'healthy' | 'unhealthy'
  latency_ms: number
  error: string | null
}

export interface ReadinessResponse {
  status: 'healthy' | 'degraded'
  services: Record<InfrastructureServiceName, ServiceReadiness>
}

export interface ErrorResponse {
  error: {
    code: string
    message: string
    details: unknown | null
  }
}
