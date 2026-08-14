import { ApiError } from './client'

export interface MessageStartEvent { event: 'message_start', data: { conversation_id: string } }
export interface AgentStatusEvent { event: 'agent_status', data: { status: string } }
export interface RetrievalStartEvent { event: 'retrieval_start', data: Record<string, unknown> }
export interface RetrievalResultEvent { event: 'retrieval_result', data: Record<string, unknown> }
export interface TokenEvent { event: 'token', data: { text: string } }
export interface CitationData {
  source_label: string
  document_id: string
  chunk_id: string
  quote: string
  page_number: number | null
  section: string | null
  score: number | null
}
export interface CitationEvent { event: 'citation', data: CitationData }
export interface MessageEndEvent { event: 'message_end', data: { content: string } }
export interface ErrorEvent { event: 'error', data: { message: string } }

export type SseEvent = MessageStartEvent | AgentStatusEvent | RetrievalStartEvent
  | RetrievalResultEvent | TokenEvent | CitationEvent | MessageEndEvent | ErrorEvent

export interface StreamConversationOptions {
  signal?: AbortSignal
}

export async function* streamConversationMessage(
  conversationId: string,
  content: string,
  options: StreamConversationOptions = {},
): AsyncGenerator<SseEvent> {
  const response = await fetch(`/api/v1/conversations/${encodeURIComponent(conversationId)}/messages/stream`, {
    method: 'POST',
    headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
    signal: options.signal,
  })
  await throwForError(response)
  if (!response.body) return

  const decoder = new TextDecoder()
  const reader = response.body.getReader()
  let buffer = ''
  let eventName = ''
  let dataLines: string[] = []

  function dispatch(): SseEvent | undefined {
    const name = eventName
    const data = dataLines.join('\n')
    eventName = ''
    dataLines = []
    if (!name || !data) return undefined
    try {
      return toSseEvent(name, JSON.parse(data) as unknown)
    } catch {
      return undefined
    }
  }

  function consumeLine(line: string): SseEvent | undefined {
    if (line === '') return dispatch()
    if (line.startsWith(':')) return undefined
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') eventName = value
    if (field === 'data') dataLines.push(value)
    return undefined
  }

  function drain(final: boolean): SseEvent[] {
    const events: SseEvent[] = []
    while (true) {
      const newline = buffer.search(/[\r\n]/)
      if (newline === -1) break
      if (!final && buffer[newline] === '\r' && newline === buffer.length - 1) break
      const line = buffer.slice(0, newline)
      const endingLength = buffer[newline] === '\r' && buffer[newline + 1] === '\n' ? 2 : 1
      buffer = buffer.slice(newline + endingLength)
      const event = consumeLine(line)
      if (event) events.push(event)
    }
    if (final && buffer) {
      const event = consumeLine(buffer)
      buffer = ''
      if (event) events.push(event)
    }
    return events
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    for (const event of drain(false)) yield event
  }
  buffer += decoder.decode()
  for (const event of drain(true)) yield event
  const finalEvent = dispatch()
  if (finalEvent) yield finalEvent
}

function toSseEvent(event: string, data: unknown): SseEvent | undefined {
  if (!isRecord(data)) return undefined
  switch (event) {
    case 'message_start':
      return typeof data.conversation_id === 'string' ? { event, data: { conversation_id: data.conversation_id } } : undefined
    case 'agent_status':
      return typeof data.status === 'string' ? { event, data: { status: data.status } } : undefined
    case 'retrieval_start':
    case 'retrieval_result':
      return { event, data }
    case 'token':
      return typeof data.text === 'string' ? { event, data: { text: data.text } } : undefined
    case 'citation':
      return isCitation(data) ? { event, data } : undefined
    case 'message_end':
      return typeof data.content === 'string' ? { event, data: { content: data.content } } : undefined
    case 'error':
      return typeof data.message === 'string' ? { event, data: { message: data.message } } : undefined
    default:
      return undefined
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isCitation(value: Record<string, unknown>): value is CitationData & Record<string, unknown> {
  return typeof value.source_label === 'string'
    && typeof value.document_id === 'string'
    && typeof value.chunk_id === 'string'
    && typeof value.quote === 'string'
    && (value.page_number === null || typeof value.page_number === 'number')
    && (value.section === null || typeof value.section === 'string')
    && (value.score === null || typeof value.score === 'number')
}

async function throwForError(response: Response): Promise<void> {
  if (response.ok) return
  if (response.headers.get('content-type')?.includes('application/json')) {
    try {
      const payload: unknown = await response.json()
      if (isRecord(payload) && isRecord(payload.error)
        && typeof payload.error.code === 'string' && typeof payload.error.message === 'string') {
        throw new ApiError(response.status, payload.error.code, payload.error.message, payload.error.details)
      }
    } catch (error) {
      if (error instanceof ApiError) throw error
    }
  }
  throw new ApiError(response.status, 'http_error', `Request failed with status ${response.status}`)
}
