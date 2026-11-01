import type { Command } from './types'
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message)
  }
}
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'content-type': 'application/json', 'x-avenboard-request': '1' },
    credentials: 'same-origin',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok) {
    const detail = data.detail
    throw new ApiError(
      data.message ||
        detail?.message ||
        (typeof detail === 'string' ? detail : 'Check the fields and try again.'),
      response.status
    )
  }
  return data
}
export function command<T = Record<string, unknown>>(body: Command): Promise<T> {
  return api('/commands', { ...body, operation_id: body.operation_id || crypto.randomUUID() })
}
