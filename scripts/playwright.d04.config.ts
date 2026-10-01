import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './src/tests/integration',
  fullyParallel: false,
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 120_000 },
  reporter: 'list',
  outputDir: 'test-results/playwright-d04',
  use: {
    baseURL: process.env.D04_BASE_URL ?? 'https://homex.internal',
    headless: true,
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
})
