import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1,
  testMatch: process.env.B1_API_INTEGRATION === '1' ? 'api-flow.spec.ts' : 'b1-flow.spec.ts',
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', headless: true, trace: 'retain-on-failure' },
  webServer: [
    { command: 'npm run dev', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI },
  ],
});
