import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
let ready = false
for (let attempt = 0; attempt < 30 && !ready; attempt++) {
  try {
    ready = (await fetch('http://127.0.0.1:8080/healthz')).ok
  } catch {
    /* wait for startup */
  }
  if (!ready) await new Promise((resolve) => setTimeout(resolve, 1000))
}
if (!ready) throw new Error('Start the local QA preview before capturing screenshots.')
const browser = await chromium.launch()
await mkdir('../docs/screenshots', { recursive: true })
const errors = []
try {
  for (const [name, width, height] of [
    ['desktop', 1440, 1000],
    ['tablet', 820, 1180],
    ['mobile', 390, 844],
  ]) {
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 })
    page.on('pageerror', (e) => errors.push(name + ': ' + e.message))
    await page.goto('http://127.0.0.1:8080/')
    await page.getByRole('heading', { name: /Good day/ }).waitFor()
    if (width < 700) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
    await page.getByRole('button', { name: 'Light theme', exact: true }).click()
    if (width < 700) await page.getByRole('button', { name: 'Close navigation', exact: true }).click()
    await page.screenshot({
      path: '../docs/screenshots/' + name + '-light.png',
      fullPage: true,
      animations: 'disabled',
    })
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
    if (overflow) errors.push(name + ': document overflow')
    if (width < 700) await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
    await page.getByRole('button', { name: 'Dark theme', exact: true }).click()
    if (width < 700) await page.getByRole('button', { name: 'Close navigation', exact: true }).click()
    await page.screenshot({
      path: '../docs/screenshots/' + name + '-dark.png',
      fullPage: true,
      animations: 'disabled',
    })
    await page.getByRole('button', { name: 'Open Product Development', exact: true }).click()
    await page.getByRole('button', { name: 'Design new landing page', exact: true }).waitFor()
    await page.screenshot({
      path: '../docs/screenshots/' + name + '-board.png',
      fullPage: true,
      animations: 'disabled',
    })
    await page.getByRole('button', { name: 'Design new landing page', exact: true }).click()
    await page.getByRole('dialog').waitFor()
    await page.screenshot({
      path: '../docs/screenshots/' + name + '-card.png',
      fullPage: true,
      animations: 'disabled',
    })
    await page.close()
  }
} finally {
  await browser.close()
}
const result = { environment: 'Local labeled QA fixtures, not deployed evidence', screenshots: 12, errors }
await writeFile('../docs/evidence/visual-audit.json', JSON.stringify(result, null, 2) + '\n')
console.log(JSON.stringify(result, null, 2))
if (errors.length) process.exitCode = 1
