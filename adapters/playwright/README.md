# Playwright adapter

Produces the `scenario-results.json` that `scripts/check_coverage.py` consumes, from the runner itself rather than
from the agent's hand. Two TypeScript files, no dependencies beyond `@playwright/test` (>= 1.42 for test tags;
Playwright loads TS reporters and helpers natively). Copy the directory into your project or reference it by
relative path, as `examples/web-demo` does.

## Configure

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';
import type { PrdReporterOptions } from './adapters/playwright/prd-reporter';

const prd: PrdReporterOptions = {
  outputFile: 'evidence/scenario-results.json', // relative to this config file
  artifactRoot: '.',                             // what you pass to check_coverage.py --artifact-root
  evidenceDir: 'evidence',                       // <artifactRoot>/<evidenceDir>/<AC>/ receives trace + screenshots; wiped per run
  prdId: 'PRD-007',
  // prototypeVersion: 'abc123',                 // else env PROTOTYPE_VERSION, else git short SHA, else "unversioned"
};

export default defineConfig({
  reporter: [['list'], ['./adapters/playwright/prd-reporter.ts', prd]],
  use: { trace: 'on' }, // the trace attachment becomes the AC's `recording`
});
```

## Author a scenario

```ts
import { test, expect } from '@playwright/test';
import { expectScreen } from './adapters/playwright/screens';

test('AC-01 happy path', { tag: '@AC-01' }, async ({ page, request }, testInfo) => {
  await request.post('/__test/reset', { data: {} });            // seed the fake first
  await page.goto('/');                                          // start where the user starts
  await expectScreen(testInfo, 'S1', page.getByRole('heading', { name: 'Home' }));
  await page.getByRole('link', { name: 'Profile' }).click();
  await expectScreen(testInfo, 'S2', page.getByRole('heading', { name: 'Profile' }));
  // ...assertions
});
```

`expectScreen(testInfo, screenId, locator)` awaits `expect(locator).toBeVisible()`; only after that passes does it
record the visit (a `prd-screen` annotation) and attach a full-page screenshot named `<AC>-<screen>.png`. A failing
assertion records nothing, so a route list or a screenshot directory can never pass as a visit.

Rules the reporter enforces:

- Exactly one `@AC-<id>` tag per test (e.g. `@AC-01`, `@AC-login-3`). Zero or several: the row is written with `status: "failed"` and an `error`,
  the message is printed, and the run exit status is failed. Nothing is guessed.
- Retries: the last attempt is the row. Two tests tagged with the same AC produce two rows; the checker flags the
  duplicate rather than the reporter merging them.
- `entry_screen` is the first recorded visit. Artifact paths are relative to `artifactRoot`, land under
  `<evidenceDir>/<AC>/`, and are unique per file (`-2`, `-3` suffixes when a screen is visited twice).

## Check

```bash
npx playwright test
python3 scripts/check_coverage.py --contract coverage-contract.json \
  --results evidence/scenario-results.json --artifact-root .
```

Output shape:

```json
{
  "prd_id": "PRD-007", "prototype_version": "a1b2c3d",
  "run_started_at": "2026-10-03T08:00:00.000Z",
  "runner": {"name": "playwright", "version": "1.63.0"},
  "results": [{"id": "AC-01", "status": "passed", "entry_screen": "S1", "visited_screens": ["S1", "S2"],
               "recording": "evidence/AC-01/trace.zip", "screenshots": ["evidence/AC-01/AC-01-S1.png", "evidence/AC-01/AC-01-S2.png"]}],
  "review": {"status": "pending"}
}
```
