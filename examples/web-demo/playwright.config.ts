import { defineConfig } from '@playwright/test';
import type { PrdReporterOptions } from '../../adapters/playwright/prd-reporter';

const PORT = 4312;

const prdReporter: PrdReporterOptions = {
  outputFile: 'evidence/scenario-results.json',
  artifactRoot: '.',
  evidenceDir: 'evidence',
  prdId: 'PRD-DEMO-001',
};

export default defineConfig({
  testDir: 'tests',
  workers: 1, // the fake backend is one shared in-memory state; tests reset it, so they must not interleave
  retries: 0,
  reporter: [['list'], ['../../adapters/playwright/prd-reporter.ts', prdReporter]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on',
  },
  webServer: {
    command: 'node server.js',
    env: { PROTOTYPE_MODE: '1', PORT: String(PORT) },
    port: PORT,
    reuseExistingServer: false,
  },
});
