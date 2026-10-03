import { test, expect, type Page, type APIRequestContext, type TestInfo } from '@playwright/test';
import { expectScreen } from '../../../adapters/playwright/screens';

// Seed the fake, start where the user starts (S1), assert it, then navigate to the profile (S2).
async function openProfile(page: Page, request: APIRequestContext, testInfo: TestInfo, seed: object = {}) {
  await request.post('/__test/reset', { data: seed });
  await page.goto('/');
  await expectScreen(testInfo, 'S1', page.getByRole('heading', { name: 'Home' }));
  await page.getByRole('link', { name: 'Profile' }).click();
  await expectScreen(testInfo, 'S2', page.getByRole('heading', { name: 'Profile' }));
}

test('AC-01 editor renames and the name persists after reload', { tag: '@AC-01' }, async ({ page, request }, testInfo) => {
  await openProfile(page, request, testInfo);
  await page.getByLabel('Display name').fill('Grace Hopper');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status')).toHaveText('Saved as "Grace Hopper".');
  await page.reload();
  await expect(page.getByTestId('current-name')).toHaveText('Grace Hopper');
  await page.getByRole('link', { name: 'Home' }).click();
  await expect(page.getByTestId('home-name')).toHaveText('Grace Hopper');
});

test('AC-02 blank name is rejected and the stored name is kept', { tag: '@AC-02' }, async ({ page, request }, testInfo) => {
  await openProfile(page, request, testInfo);
  await page.getByLabel('Display name').fill('   ');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('alert')).toHaveText('Display name cannot be blank.');
  await page.reload();
  await expect(page.getByTestId('current-name')).toHaveText('Ada Lovelace');
});

test('AC-03 stale revision conflict keeps the draft', { tag: '@AC-03' }, async ({ page, request }, testInfo) => {
  await openProfile(page, request, testInfo);
  await page.getByLabel('Display name').fill('Draft Name');
  // Someone else saves first: the fake now holds revision 2, the page still submits revision 1.
  const other = await request.put('/api/profile', { data: { name: 'Other Editor', revision: 1 } });
  expect(other.ok()).toBe(true);
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('alert')).toHaveText('Profile changed elsewhere. Your draft is kept.');
  await expect(page.getByLabel('Display name')).toHaveValue('Draft Name');
  await page.reload();
  await expect(page.getByTestId('current-name')).toHaveText('Other Editor');
});

test('AC-04 viewer cannot save: rejected at the fake command boundary', { tag: '@AC-04' }, async ({ page, request }, testInfo) => {
  await openProfile(page, request, testInfo, { actor: 'viewer' });
  await expect(page.getByTestId('actor')).toHaveText('viewer');
  await page.getByLabel('Display name').fill('Sneaky Viewer');
  await page.getByRole('button', { name: 'Save' }).click(); // the control is reachable; the boundary says no
  await expect(page.getByRole('alert')).toHaveText('Viewers cannot edit the display name.');
  const stored = await (await request.get('/api/profile')).json();
  expect(stored).toEqual({ name: 'Ada Lovelace', revision: 1 });
});
