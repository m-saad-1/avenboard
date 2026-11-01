import { chromium } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
const browser = await chromium.launch()
const samples = []
for (const [device, width, height] of [
  ['desktop', 1440, 1000],
  ['mobile', 390, 844],
]) {
  for (let sample = 1; sample <= 3; sample++) {
    const context = await browser.newContext({ viewport: { width, height } })
    const page = await context.newPage()
    await page.addInitScript(() => {
      window.__metrics = { lcp: null, cls: 0 }
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) window.__metrics.lcp = e.startTime
      }).observe({ type: 'largest-contentful-paint', buffered: true })
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) if (!e.hadRecentInput) window.__metrics.cls += e.value
      }).observe({ type: 'layout-shift', buffered: true })
    })
    await page.goto('http://127.0.0.1:8080/')
    await page.getByRole('heading', { name: /Good day/ }).waitFor()
    await page.waitForLoadState('networkidle')
    samples.push(
      await page.evaluate(
        ({ device, sample }) => {
          const n = performance.getEntriesByType('navigation')[0]
          const resources = performance.getEntriesByType('resource')
          return {
            device,
            sample,
            ttfbMs: n.responseStart - n.requestStart,
            domContentLoadedMs: n.domContentLoadedEventEnd,
            lcpMs: window.__metrics.lcp,
            cls: window.__metrics.cls,
            resourceCount: resources.length,
            resourceTransferBytes: resources.reduce((sum, r) => sum + r.transferSize, 0),
            externalRequests: resources
              .filter((r) => new URL(r.name).origin !== location.origin)
              .map((r) => r.name),
          }
        },
        { device, sample }
      )
    )
    await context.close()
  }
}
await browser.close()
const result = {
  environment:
    'Local loopback Chromium; in-memory QA data; no network or CPU throttling; not deployed performance or Lighthouse',
  samples,
}
await writeFile('../docs/evidence/local-performance.json', JSON.stringify(result, null, 2) + '\n')
console.log(JSON.stringify(result, null, 2))
