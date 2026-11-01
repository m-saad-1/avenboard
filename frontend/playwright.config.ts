import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  use: { baseURL: 'http://127.0.0.1:8080', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  reporter: [['list'], ['json', { outputFile: '../docs/evidence/browser-results.json' }]],
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
    { name: 'tablet', use: { ...devices['Desktop Chrome'], viewport: { width: 820, height: 1180 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command:
      process.platform === 'win32'
        ? '..\\.venv\\Scripts\\python.exe -m uvicorn tests.preview:app --host 127.0.0.1 --port 8080 --app-dir ..'
        : 'cd .. && python -m uvicorn tests.preview:app --host 127.0.0.1 --port 8080',
    url: 'http://127.0.0.1:8080/healthz',
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
})
