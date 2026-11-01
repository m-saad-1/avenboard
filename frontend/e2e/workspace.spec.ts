import { test, expect, type Page } from '@playwright/test'
async function nav(page: Page, name: string) {
  if (await page.getByRole('button', { name: 'Open navigation', exact: true }).isVisible())
    await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name, exact: true })
    .click()
}
test('overview, both themes, navigation, responsive layout and safe rendering', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Good day/ })).toBeVisible()
  await expect(page.getByText(/LOCAL QA PREVIEW/)).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  for (const mode of ['Dark', 'Light']) {
    const mobile = await page.getByRole('button', { name: 'Open navigation', exact: true }).isVisible()
    if (mobile) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
    await page.getByRole('button', { name: mode + ' theme', exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', mode.toLowerCase())
    if (mobile) await page.getByRole('button', { name: 'Close navigation', exact: true }).click()
  }
  await nav(page, 'My tasks')
  await expect(page.getByRole('heading', { name: 'My tasks', exact: true })).toBeVisible()
  await nav(page, 'All boards')
  await expect(page.getByRole('heading', { name: 'All boards', exact: true })).toBeVisible()
  await nav(page, 'Favorites')
  await expect(page.getByRole('heading', { name: 'Your favorites' })).toBeVisible()
  expect(errors).toEqual([])
})
test('task create, edit, move, checklist, activity, filters and reload', async ({ page }, info) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Open Operations', exact: true }).click()
  const title = 'QA task ' + info.project.name + ' ' + Date.now()
  await page.getByRole('button', { name: 'New task', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Task title', { exact: true }).fill(title)
  await dialog.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(dialog).not.toBeVisible()
  await page.getByRole('button', { name: title, exact: true }).click()
  await page
    .getByLabel('Description', { exact: true })
    .fill('<script>alert("unsafe")</script> Review this literal text.')
  await page.getByRole('button', { name: 'Save task', exact: true }).click()
  await page.getByLabel('Status / list').selectOption({ label: 'Done' })
  await page.getByLabel('Checklist item', { exact: true }).fill('Review outcome')
  await page.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page.getByText('Review outcome', { exact: true })).toBeVisible()
  await page.getByRole('checkbox', { name: 'Review outcome' }).check()
  await page.getByRole('button', { name: 'Close dialog', exact: true }).click()
  await page.reload()
  await page.getByRole('button', { name: title, exact: true }).click()
  await expect(page.getByLabel('Status / list')).toHaveValue(
    (await page
      .getByLabel('Status / list')
      .locator('option')
      .filter({ hasText: 'Done' })
      .getAttribute('value')) as string
  )
  await expect(page.getByLabel('Description', { exact: true })).toHaveValue(
    '<script>alert("unsafe")</script> Review this literal text.'
  )
  await expect(page.getByRole('checkbox', { name: 'Review outcome' })).toBeChecked()
  await page.getByRole('button', { name: 'Close dialog', exact: true }).click()
  await page.getByRole('button', { name: 'Filter', exact: true }).click()
  await page.getByLabel('Search board').fill(title)
  await expect(page.getByText(/Clear filters to reorder/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Drag ' + title, exact: true })).toHaveCount(0)
})
test('viewer reads with no content write controls', async ({ page, context }) => {
  await context.addCookies([{ name: 'qa-role', value: 'viewer', url: 'http://127.0.0.1:8080' }])
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Good day, Cy/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create board', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Open Operations', exact: true }).click()
  await expect(page.getByRole('button', { name: 'New task', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Send client invoice', exact: true }).click()
  await expect(page.getByLabel('Task title', { exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Save task', exact: true })).toHaveCount(0)
})
test('failed mutations report the error and preserve persisted task', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Open Operations', exact: true }).click()
  await page.getByRole('button', { name: 'Send client invoice', exact: true }).click()
  await page.getByLabel('Task title', { exact: true }).fill('Unsaved')
  await page.route('**/api/commands', (route) =>
    route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Concurrent changes detected. Refresh and retry.' }),
    })
  )
  await page.getByRole('button', { name: 'Save task', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Concurrent changes')
  await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible()
  await page.getByRole('button', { name: 'Dismiss message', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByRole('button', { name: 'Close dialog', exact: true }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Send client invoice', exact: true })).toBeVisible()
})
