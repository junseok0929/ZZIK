import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';

const systemChrome = existsSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: 0,
  outputDir: '../output/playwright/test-results',
  reporter: [['list'], ['html', { outputFolder: '../output/playwright/report', open: 'never' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
    channel: systemChrome ? 'chrome' : undefined,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    { name: 'desktop', testMatch: /desktop\.spec\.ts/, use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', testMatch: /mobile\.spec\.ts/, use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } },
  ],
});
