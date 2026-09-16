import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';
export default defineConfig({
  testDir: './demo-e2e', workers: 1, timeout: 60_000,
  expect: {timeout: 10_000},
  outputDir: '../output/playwright/demo-results',
  reporter: 'list',
  use: {baseURL: 'http://127.0.0.1:5174/ZZIK/', channel: existsSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome') ? 'chrome' : undefined, viewport: {width: 1440, height: 1000}, screenshot: 'only-on-failure'},
  webServer: {command: 'npx vite preview --host 127.0.0.1 --port 5174 --strictPort --base=/ZZIK/', url: 'http://127.0.0.1:5174/ZZIK/', reuseExistingServer: false},
});
