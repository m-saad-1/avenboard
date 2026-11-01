import type { Command } from './types'
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message)
  }
}
const staticDemo = import.meta.env.VITE_STATIC_DEMO === 'true'
type StaticFixture = {
  identity: { user: { id: string }; theme: string; test_fixture?: boolean }
  workspaces: Array<{ id: string }>
  snapshot: {
    workspace: { id: string }
    boards: Array<Record<string, unknown>>
    cards: Array<Record<string, unknown>>
    activity: Array<Record<string, unknown>>
    dependencies: Array<Record<string, unknown>>
  }
}
let fixtureRequest: Promise<StaticFixture> | null = null
function staticFixture(): Promise<StaticFixture> {
  fixtureRequest ??= fetch(import.meta.env.BASE_URL + 'demo/workspace.json').then((r) => {
    if (!r.ok) throw new ApiError('The public sample workspace could not be loaded.', r.status)
    return r.json() as Promise<StaticFixture>
  })
  return fixtureRequest
}
function page<T>(items: T[], offset: number, limit: number) {
  return { items: items.slice(offset, offset + limit), total: items.length }
}
async function staticApi<T>(path: string, body?: unknown): Promise<T> {
  if (body !== undefined) {
    const payload = body as { action?: string; theme?: string }
    if (path === '/commands' && payload.action === 'preference' && payload.theme) {
      localStorage.setItem('avenboard-preview-theme', payload.theme)
      return { ok: true } as T
    }
    throw new ApiError(
      'This public dashboard is a read-only sample. Changes require the full Avenboard backend.',
      403
    )
  }
  const fixture = await staticFixture()
  const url = new URL(path, window.location.origin)
  const route = url.pathname
  const offset = Number(url.searchParams.get('offset') || 0)
  const limit = Number(url.searchParams.get('limit') || 50)
  const snapshot = fixture.snapshot
  if (route === '/me') {
    return {
      ...fixture.identity,
      theme: localStorage.getItem('avenboard-preview-theme') || fixture.identity.theme,
    } as T
  }
  if (route === '/workspaces') return fixture.workspaces as T
  const snapshotMatch = route.match(/^\/workspaces\/([^/]+)\/snapshot$/)
  if (snapshotMatch && decodeURIComponent(snapshotMatch[1]) === snapshot.workspace.id) return snapshot as T
  if (route === '/cards') {
    const query = (url.searchParams.get('query') || '').trim().toLocaleLowerCase()
    let cards = snapshot.cards.filter((card) => {
      const text = `${card.title || ''} ${card.description || ''}`.toLocaleLowerCase()
      return !query || text.includes(query)
    })
    const assignee = url.searchParams.get('assignee_id')
    const label = url.searchParams.get('label_id')
    const list = url.searchParams.get('list_id')
    const status = url.searchParams.get('status')
    const overdue = url.searchParams.get('overdue') === 'true'
    if (assignee) cards = cards.filter((card) => card.assignee_id === assignee)
    if (label) cards = cards.filter((card) => (card.label_ids as string[]).includes(label))
    if (list) cards = cards.filter((card) => card.list_id === list)
    if (status) cards = cards.filter((card) => card.status === status)
    if (overdue) cards = cards.filter((card) => card.overdue === true)
    return page(cards, offset, limit) as T
  }
  const cardActivity = route.match(/^\/cards\/([^/]+)\/activity$/)
  if (cardActivity) {
    const items = snapshot.activity.filter((event) => event.card_id === decodeURIComponent(cardActivity[1]))
    return page(items, offset, limit) as T
  }
  const workspaceActivity = route.match(/^\/workspaces\/([^/]+)\/activity$/)
  if (workspaceActivity) {
    const boardId = url.searchParams.get('board_id')
    const items = snapshot.activity.filter((event) => !boardId || event.board_id === boardId)
    return page(items, offset, limit) as T
  }
  if (route === '/semantic-search') {
    throw new ApiError('AI search requires the full Avenboard backend.', 503)
  }
  throw new ApiError('This operation is not available in the read-only public sample.', 503)
}
export async function api<T>(path: string, body?: unknown): Promise<T> {
  if (staticDemo) return staticApi<T>(path, body)
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
