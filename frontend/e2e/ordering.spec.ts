import { test, expect, type Page, type Locator } from '@playwright/test'
async function drag(page: Page, source: Locator, target: Locator) {
  await source.scrollIntoViewIfNeeded()
  const a = await source.boundingBox(),
    b = await target.boundingBox()
  if (!a || !b) throw Error('Missing drag target')
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
  await page.mouse.down()
  await page.mouse.move(a.x + a.width / 2 + 10, a.y + a.height / 2, { steps: 3 })
  await page.mouse.move(b.x + b.width / 2, b.y + Math.min(b.height / 2, 60), { steps: 14 })
  await page.mouse.up()
}
test('pointer moves to an empty list, reorders cards and lists, and survives reload', async ({
  page,
  request,
}, info) => {
  test.skip(info.project.name === 'mobile', 'Separate touch test below')
  const run = async (body: object) => {
    const r = await request.post('/api/commands', { data: body, headers: { 'x-avenboard-request': '1' } })
    expect(r.ok()).toBeTruthy()
    return r.json()
  }
  const spaces = await (await request.get('/api/workspaces')).json()
  const board = await run({
    action: 'create_board',
    workspace_id: spaces[0].id,
    title: 'Ordering ' + Date.now(),
  })
  let data = await (await request.get('/api/boards/' + board.id)).json()
  const [backlog, todo] = data.lists
  const first = await run({ action: 'create_card', list_id: backlog.id, title: 'Drag first' }),
    second = await run({ action: 'create_card', list_id: backlog.id, title: 'Drag second' })
  await page.goto('/#board/' + board.id)
  await drag(
    page,
    page.getByRole('button', { name: 'Drag Drag first', exact: true }),
    page.getByRole('region', { name: 'Todo', exact: true }).locator('.drop-empty')
  )
  await expect(
    page
      .getByRole('region', { name: 'Todo', exact: true })
      .getByRole('button', { name: 'Drag first', exact: true })
  ).toBeVisible()
  await page.reload()
  await expect(
    page
      .getByRole('region', { name: 'Todo', exact: true })
      .getByRole('button', { name: 'Drag first', exact: true })
  ).toBeVisible()
  await drag(
    page,
    page.getByRole('button', { name: 'Drag Drag second', exact: true }),
    page.getByRole('region', { name: 'Todo', exact: true }).locator('.task-card')
  )
  await expect(page.getByRole('region', { name: 'Todo', exact: true }).locator('.task-card')).toHaveCount(2)
  await drag(
    page,
    page.getByRole('button', { name: 'Drag list Backlog', exact: true }),
    page.getByRole('region', { name: 'Todo', exact: true }).locator('.column-header')
  )
  await expect
    .poll(async () => {
      const result = await (await request.get('/api/boards/' + board.id)).json()
      return result.lists[0].id
    })
    .toBe(todo.id)
  await page.reload()
  await expect(page.locator('.board-column').first()).toHaveAttribute('aria-label', 'Todo')
  data = await (await request.get('/api/boards/' + board.id)).json()
  expect(
    data.cards
      .filter((c: any) => c.list_id === todo.id)
      .map((c: any) => c.position)
      .sort()
  ).toEqual([0, 1])
})
test('touch dragging moves a task into an empty list', async ({ page, request, context }, info) => {
  test.skip(info.project.name !== 'mobile', 'Touch viewport only')
  const run = async (body: object) =>
    (await request.post('/api/commands', { data: body, headers: { 'x-avenboard-request': '1' } })).json()
  const spaces = await (await request.get('/api/workspaces')).json(),
    board = await run({ action: 'create_board', workspace_id: spaces[0].id, title: 'Touch ' + Date.now() })
  const data = await (await request.get('/api/boards/' + board.id)).json()
  await run({ action: 'create_card', list_id: data.lists[0].id, title: 'Touch task' })
  await page.goto('/#board/' + board.id)
  const handle = page.getByRole('button', { name: 'Drag Touch task', exact: true })
  await handle.waitFor()
  await handle.scrollIntoViewIfNeeded()
  const a = await handle.boundingBox(),
    target = await page
      .getByRole('region', { name: 'Todo', exact: true })
      .locator('.drop-empty')
      .boundingBox()
  expect(a && target).toBeTruthy()
  const client = await context.newCDPSession(page),
    x = a!.x + a!.width / 2,
    y = a!.y + a!.height / 2,
    endX = Math.min(target!.x + 40, 390),
    endY = target!.y + 30
  await client.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] })
  await page.waitForTimeout(60)
  for (let i = 1; i <= 12; i++) {
    await client.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ x: x + ((endX - x) * i) / 12, y: y + ((endY - y) * i) / 12 }],
    })
    await page.waitForTimeout(16)
  }
  await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await expect
    .poll(async () => {
      const b = await (await request.get('/api/boards/' + board.id)).json()
      return b.cards[0].list_id
    })
    .toBe(data.lists[1].id)
})
test('keyboard dragging and focus restoration', async ({ page, request }, info) => {
  test.skip(info.project.name === 'mobile', 'Physical keyboard desktop check')
  const spaces = await (await request.get('/api/workspaces')).json()
  const board = await (
    await request.post('/api/commands', {
      data: { action: 'create_board', workspace_id: spaces[0].id, title: 'Keyboard ' + Date.now() },
      headers: { 'x-avenboard-request': '1' },
    })
  ).json()
  const data = await (await request.get('/api/boards/' + board.id)).json()
  await request.post('/api/commands', {
    data: { action: 'create_card', list_id: data.lists[0].id, title: 'Keyboard task' },
    headers: { 'x-avenboard-request': '1' },
  })
  await page.goto('/#board/' + board.id)
  const handle = page.getByRole('button', { name: 'Drag Keyboard task', exact: true })
  await handle.focus()
  await page.keyboard.press('Space')
  await expect(handle).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('[role="status"]')).toContainText('Keyboard task')
  await page.keyboard.press('ArrowRight')
  await expect(page.locator('[role="status"]')).toContainText('Over Todo')
  await page.keyboard.press('Space')
  await expect
    .poll(async () => {
      const b = await (await request.get('/api/boards/' + board.id)).json()
      return b.cards[0].list_id
    })
    .toBe(data.lists[1].id)
  const title = page.getByRole('button', { name: 'Keyboard task', exact: true })
  await title.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(title).toBeFocused()
})

test('failed drag rolls back the optimistic move', async ({ page, request }, info) => {
  test.skip(info.project.name === 'mobile', 'Pointer failure path; touch success is tested separately')
  const run = async (data: object) =>
    (
      await request.post('/api/commands', {
        data,
        headers: { 'x-avenboard-request': '1' },
      })
    ).json()
  const spaces = await (await request.get('/api/workspaces')).json()
  const board = await run({
    action: 'create_board',
    workspace_id: spaces[0].id,
    title: 'Rollback ' + Date.now(),
  })
  const data = await (await request.get('/api/boards/' + board.id)).json()
  await run({ action: 'create_card', list_id: data.lists[0].id, title: 'Rollback task' })
  await page.goto('/#board/' + board.id)
  await page.route('**/api/commands', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Service temporarily unavailable' }),
    })
  )
  await drag(
    page,
    page.getByRole('button', { name: 'Drag Rollback task', exact: true }),
    page.getByRole('region', { name: 'Todo', exact: true }).locator('.drop-empty')
  )
  await expect(page.getByRole('alert')).toContainText('temporarily unavailable')
  await expect(
    page
      .getByRole('region', { name: 'Backlog', exact: true })
      .getByRole('button', { name: 'Rollback task', exact: true })
  ).toBeVisible()
  await page.reload()
  await expect(
    page
      .getByRole('region', { name: 'Backlog', exact: true })
      .getByRole('button', { name: 'Rollback task', exact: true })
  ).toBeVisible()
})

test('two browser sessions reject a stale move and preserve the first change', async ({
  page,
  request,
  browser,
}) => {
  const run = async (data: object) =>
    (
      await request.post('/api/commands', {
        data,
        headers: { 'x-avenboard-request': '1' },
      })
    ).json()
  const spaces = await (await request.get('/api/workspaces')).json()
  const board = await run({
    action: 'create_board',
    workspace_id: spaces[0].id,
    title: 'Concurrent ' + Date.now(),
  })
  const data = await (await request.get('/api/boards/' + board.id)).json()
  await run({ action: 'create_card', list_id: data.lists[0].id, title: 'Concurrent task' })
  const secondContext = await browser.newContext()
  await secondContext.addCookies([{ name: 'qa-role', value: 'member', url: 'http://127.0.0.1:8080' }])
  const second = await secondContext.newPage()
  try {
    for (const p of [page, second]) {
      await p.goto('http://127.0.0.1:8080/#board/' + board.id)
      await p.getByRole('button', { name: 'Concurrent task', exact: true }).click()
    }
    const saved = page.waitForResponse(
      (r) => r.url().endsWith('/api/commands') && r.request().method() === 'POST'
    )
    await page.getByLabel('Status / list').selectOption({ label: 'Todo' })
    expect((await saved).status()).toBe(200)
    const stale = second.waitForResponse(
      (r) => r.url().endsWith('/api/commands') && r.request().method() === 'POST'
    )
    await second.getByLabel('Status / list').selectOption({ label: 'Done' })
    expect((await stale).status()).toBe(409)
    await second.getByRole('button', { name: 'Close dialog', exact: true }).click()
    await second.reload()
    await expect(
      second
        .getByRole('region', { name: 'Todo', exact: true })
        .getByRole('button', { name: 'Concurrent task', exact: true })
    ).toBeVisible()
    const final = await (await request.get('/api/boards/' + board.id)).json()
    expect(final.cards[0].list_id).toBe(data.lists[1].id)
  } finally {
    await secondContext.close()
  }
})
