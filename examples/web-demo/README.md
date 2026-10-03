# web-demo

The whole evidence loop on a toy feature (PRD-DEMO-001, "edit display name on profile"):

1. `PRD.md` fixes four acceptance scenarios across two screens (S1 home, S2 profile).
2. `server.js` serves a plain HTML/JS app plus a stateful fake backend. `PROTOTYPE_MODE=1` adds the test-only
   `POST /__test/reset` seed endpoint; without it the endpoint does not exist. Actor and revision guards live in
   the fake's command boundary, not only in the UI.
3. `tests/edit-display-name.spec.ts` has one Playwright test per AC, each tagged `@AC-NN`, each starting at Home and
   recording screen visits with `expectScreen` from `../../adapters/playwright`.
4. The `prd-reporter` writes `evidence/scenario-results.json` and copies each AC's trace and screenshots into
   `evidence/<AC>/`. Nothing in the results file is written by hand.
5. `scripts/check_coverage.py` gates the result against `coverage-contract.json`.

## Run

```bash
npm ci
npx playwright install chromium   # add --with-deps on a bare Linux box
npm test
npm run check
```

`npm run check` exits 0 when every AC has a final passing result, visited S1 then S2, and references real
artifacts under `evidence/`. Break any assertion in the spec and it exits 1.
