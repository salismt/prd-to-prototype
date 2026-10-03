import type { Locator, TestInfo } from '@playwright/test';
import { createRequire } from 'node:module';
import path from 'node:path';

export const SCREEN_ANNOTATION = 'prd-screen';
const AC_TAG = /^@(AC-\S+)$/;

/** AC ids from a test's tags. Exactly one is valid; the reporter flags anything else. */
export function acIds(tags: readonly string[]): string[] {
  return tags.map((t) => AC_TAG.exec(t)?.[1]).filter((id): id is string => !!id);
}

/**
 * Assert `locator` is visible, THEN record a visit to `screenId` and attach a
 * full-page screenshot named `<AC>-<screen>.png`. A failed assertion records nothing.
 */
export async function expectScreen(testInfo: TestInfo, screenId: string, locator: Locator): Promise<void> {
  await playwright(testInfo).expect(locator).toBeVisible();
  testInfo.annotations.push({ type: SCREEN_ANNOTATION, description: screenId });
  const ac = acIds(testInfo.tags)[0] ?? 'untagged';
  await testInfo.attach(`${ac}-${screenId}.png`, {
    body: await locator.page().screenshot({ fullPage: true }),
    contentType: 'image/png',
  });
}

// Resolve @playwright/test from the project under test, so this file may live outside its node_modules tree
// (e.g. a shared adapters/ directory). The test file already loaded that same module, so `expect` is the same instance.
function playwright(testInfo: TestInfo): typeof import('@playwright/test') {
  const from = testInfo.config.configFile ?? path.join(testInfo.config.rootDir, 'playwright.config.ts');
  return createRequire(from)('@playwright/test');
}
