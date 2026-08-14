import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

function readText(relativeUrl: string): string {
  const path = fileURLToPath(new URL(relativeUrl, import.meta.url))
  return existsSync(path) ? readFileSync(path, 'utf8') : ''
}

function composeService(compose: string, service: string): string {
  return compose.match(new RegExp(`^  ${service}:\\r?\\n([\\s\\S]*?)(?=^  \\S|^volumes:)`, 'm'))?.[0] ?? ''
}

describe('frontend delivery configuration', () => {
  it('preserves streaming API responses and serves SPA deep links through Nginx', () => {
    const nginx = readText('../nginx.conf')

    expect(nginx).toMatch(/listen\s+8080;/)
    expect(nginx).toMatch(/location\s+\/api\/v1\/\s*{[\s\S]*proxy_pass\s+http:\/\/api:8000;/)
    expect(nginx).toMatch(/location\s+\/api\/v1\/\s*{[\s\S]*proxy_http_version\s+1\.1;/)
    expect(nginx).toMatch(/location\s+\/api\/v1\/\s*{[\s\S]*proxy_buffering\s+off;/)
    expect(nginx).toMatch(/location\s+\/api\/v1\/\s*{[\s\S]*proxy_read_timeout\s+300s;/)
    expect(nginx).toMatch(/location\s+\/\s*{[\s\S]*try_files\s+\$uri\s+\$uri\/\s+\/index\.html;/)
  })

  it('publishes the frontend on loopback and waits for a healthy API', () => {
    const compose = readText('../../docker-compose.yml')
    const frontend = composeService(compose, 'frontend')

    expect(frontend).toMatch(/127\.0\.0\.1:\$\{RAG_AGENT_FRONTEND_PORT:-5173}:8080/)
    expect(frontend).toMatch(/depends_on:\s*[\s\S]*api:\s*[\s\S]*condition:\s*service_healthy/)
    expect(frontend).toMatch(/healthcheck:\s*[\s\S]*http:\/\/127\.0\.0\.1:8080\//)
  })

  it('uses an overridable same-origin development proxy without stream buffering', () => {
    const vite = readText('../vite.config.ts')

    expect(vite).toContain('VITE_API_PROXY_TARGET')
    expect(vite).toContain('http://127.0.0.1:8000')
    expect(vite).toMatch(/["']\/api\/v1["']\s*:/)
    expect(vite).toContain('x-accel-buffering')
    expect(vite).toMatch(/["']no["']/)
  })
})
