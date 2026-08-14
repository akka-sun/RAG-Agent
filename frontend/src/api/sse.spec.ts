import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './client'
import { streamConversationMessage, type SseEvent } from './sse'

const encoder = new TextEncoder()

function streamingResponse(chunks: Array<string | Uint8Array>): Response {
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(typeof chunk === 'string' ? encoder.encode(chunk) : chunk)
      controller.close()
    },
  }), { headers: { 'content-type': 'text/event-stream' } })
}

async function collect(stream: AsyncIterable<SseEvent>): Promise<SseEvent[]> {
  const events: SseEvent[] = []
  for await (const event of stream) events.push(event)
  return events
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamConversationMessage', () => {
  it('posts JSON to the encoded conversation stream endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(streamingResponse([]))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await collect(streamConversationMessage('conversation/one', 'hello', { signal: controller.signal }))

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/conversations/conversation%2Fone/messages/stream', {
      method: 'POST',
      headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: 'hello' }),
      signal: controller.signal,
    })
  })

  it('preserves split UTF-8 characters and split CRLF frame boundaries', async () => {
    const bytes = encoder.encode('event: token\r\ndata: {"text":"你好"}\r\n\r\n')
    const splitInsideChineseCharacter = bytes.findIndex((byte) => byte > 127) + 1
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamingResponse([
      bytes.slice(0, splitInsideChineseCharacter),
      bytes.slice(splitInsideChineseCharacter, bytes.length - 1),
      bytes.slice(bytes.length - 1),
    ])))

    await expect(collect(streamConversationMessage('c1', 'hi'))).resolves.toEqual([
      { event: 'token', data: { text: '你好' } },
    ])
  })

  it('handles comments, unknown fields, multiple data lines, blank data, and a final unclosed frame', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamingResponse([
      ': keepalive\nretry: 1000\nevent: token\ndata: {"text":\ndata: "hello"}\n\n',
      'event: token\ndata:\n\nevent: unknown\ndata: {"ignored":true}\n\n',
      'event: message_end\ndata: {"content":"done"}',
    ])))

    await expect(collect(streamConversationMessage('c1', 'hi'))).resolves.toEqual([
      { event: 'token', data: { text: 'hello' } },
      { event: 'message_end', data: { content: 'done' } },
    ])
  })

  it('accepts all known event shapes and ignores malformed payloads', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamingResponse([
      'event: message_start\ndata: {"conversation_id":"c1"}\n\n',
      'event: agent_status\ndata: {"status":"thinking"}\n\n',
      'event: retrieval_start\ndata: {"query":"q"}\n\n',
      'event: retrieval_result\ndata: {"count":2}\n\n',
      'event: citation\ndata: {"source_label":"[1]","document_id":"d1","chunk_id":"k1","quote":"q","page_number":1,"section":null,"score":0.9}\n\n',
      'event: error\ndata: {"message":"failed"}\n\n',
      'event: token\ndata: {"text":42}\n\n',
      'event: message_start\ndata: not-json\n\n',
    ])))

    await expect(collect(streamConversationMessage('c1', 'hi'))).resolves.toEqual([
      { event: 'message_start', data: { conversation_id: 'c1' } },
      { event: 'agent_status', data: { status: 'thinking' } },
      { event: 'retrieval_start', data: { query: 'q' } },
      { event: 'retrieval_result', data: { count: 2 } },
      { event: 'citation', data: { source_label: '[1]', document_id: 'd1', chunk_id: 'k1', quote: 'q', page_number: 1, section: null, score: 0.9 } },
      { event: 'error', data: { message: 'failed' } },
    ])
  })

  it('normalizes structured and generic HTTP errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(
      JSON.stringify({ error: { code: 'invalid_message', message: 'bad input', details: { field: 'content' } } }),
      { status: 422, headers: { 'content-type': 'application/json' } },
    )).mockResolvedValueOnce(new Response('gateway failed', { status: 502 })))

    const structuredError = await collect(streamConversationMessage('c1', 'hi')).catch((error: unknown) => error)
    expect(structuredError).toBeInstanceOf(ApiError)
    expect(structuredError).toMatchObject({ status: 422, code: 'invalid_message', message: 'bad input', details: { field: 'content' } })
    await expect(collect(streamConversationMessage('c1', 'hi'))).rejects.toEqual(expect.objectContaining({
      status: 502, code: 'http_error', message: 'Request failed with status 502',
    }))
  })

  it('propagates an intentional abort without converting it to ApiError', async () => {
    const controller = new AbortController()
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async (_url, init: RequestInit) => {
      return new Response(new ReadableStream<Uint8Array>({
        start(streamController) {
          init.signal?.addEventListener('abort', () => streamController.error(new DOMException('Aborted', 'AbortError')))
        },
      }))
    }))

    const reading = collect(streamConversationMessage('c1', 'hi', { signal: controller.signal }))
    controller.abort()

    await expect(reading).rejects.toMatchObject({ name: 'AbortError' })
  })
})
