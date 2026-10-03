---
name: prd-to-prototype
description: Turn a PRD for a web app or website feature into a clickable prototype of the existing app running on a stateful mock backend, with Playwright acceptance tests as evidence, before the backend is built. Use for PRD-driven feature discovery and product-owner review of web UI; not for backend-only work, native mobile or desktop apps, or production deployment.
license: MIT
metadata:
  author: salismt
  version: "1.1.0"
---

# PRD to Prototype (web)

The prototype is a pinned copy of the real web app, extended with the proposed UI and run against a fake backend at its existing API seam. Each PRD acceptance case (AC) becomes a Playwright journey that starts at the normal entry point, fails before the feature exists, and passes after. The checker proves every AC has a real passing run with recorded screens and artifacts. A green fake suite is **ready for product review**, nothing more.

Scope: web apps and websites. Native mobile and desktop are not supported in this version.

Resources: [PRD template](assets/prd-template.md), [web mock seams](references/web-mocks.md), [evidence contract](references/evidence.md), [Playwright adapter](adapters/playwright/README.md), [runnable example](examples/web-demo/). The example JSON under `assets/` is synthetic, not evidence of a run.

Ask only for decisions that change the feature; keep working on everything else while waiting.

## 1. Locate and understand the live UI

Every codebase differs in stack, architecture and conventions. Find out how this one works before writing anything.

**Do**
- Confirm where the live UI code lives: repository, path inside a monorepo, which app if there are several, and the branch or deployed commit. If the user has not said, or more than one candidate fits, ask. Do not guess from folder names.
- Read the project's agent/contributor instructions, the PRD, and the affected UI and API client code.
- Record what you find:
  - Stack: framework and version, rendering mode (SPA, SSR, static), router, package manager and workspace layout.
  - Data: API client or data layer (this is the mock seam), where session, auth and feature flags come from, and their response shapes.
  - UI: design system or component library, tokens, styling approach, layout shell (navigation, home, entry routes).
  - Conventions: folder structure, file and component naming, state management, lint/format/type rules.
  - Commands: install, start, build, lint, test; the existing test runner, if any.
- Ask the user about anything you cannot determine from code that changes the plan (for example which session or flag branch production uses, or where an undocumented API lives).

**Produces** `ui-profile.md` with the findings above, the source location and the open questions. Keep it with the PRD; copy it into the prototype in step 3 and allowlist it as an addition.

**Gate** The user has confirmed the source location. The mock seam, entry route, session/flag source, start command and test runner are identified, or recorded as open questions. Later steps follow the conventions in this profile, not your defaults.

## 2. Acceptance contract

**Do**
- Keep stable requirement (`FR-xx`), acceptance (`AC-xx`) and screen (`Sx`) IDs. Use the PRD template if the PRD lacks them.
- Each AC states Given (fixture, actor, flags, starting state), When (entry route plus named UI actions), Then (visible outcome plus resulting state), and its required screens.
- Include the feature's negative cases: validation, role boundaries, empty/error/retry, stale data, duplicates, concurrent changes. Mark unresolved domain rules as explicit unknowns.
- Classify any discrepancy between PRD and existing UI as clarification, defect or new scope. Record the decision in the PRD; never edit an AC expectation to make the UI pass.

**Produces** `<prototype>/coverage-contract.json` (`prd_id`, `entry_screens`, `screens`, `acceptance[]`) and the updated PRD.

**Gate** Every AC has an entry screen, required screens and an observable Then. Product owner has seen the contract or an open question is recorded.

## 3. Fresh baseline snapshot

**Do**
- Pin the source commit (deployed commit if known, otherwise the requested ref; state the difference). Fetch first.
- Copy the UI source, shared packages, lockfiles and build config identified in `ui-profile.md` into an isolated prototype directory:
  ```bash
  python3 scripts/snapshot.py create --repo /path/to/app --remote origin --fetch --ref origin/main \
    --path frontend --destination /path/to/prototypes/PRD-007
  ```
  The copy is the default because prototypes often live outside the product repo, and a pinned copy with a hash manifest is reviewable and cannot silently mutate the source. If the prototype stays inside the product repo, a `git worktree add` at the pinned commit is acceptable; then review `git diff <commit> --name-status` against the same allowlist rules in step 6.
- Never reuse an earlier PRD's prototype as the baseline. Unreachable source is a recorded limitation, not fresh evidence.

**Produces** `<prototype>/` with `prototype-manifest.json` (commit, paths, file hashes, fetch status).

**Gate** The app builds and starts from the snapshot. Home route, navigation and the real session/flag response render as in the source.

## 4. Red baseline journeys

**Do**
- Add the [Playwright adapter](adapters/playwright/README.md): tag each test with its AC id (`@AC-01`), assert screens with `expectScreen(...)`, and register the reporter that writes `scenario-results.json`. If the project already uses Cypress or another runner, write an adapter that emits the same schema; see [evidence.md](references/evidence.md).
- One test per AC. Seed the fixture, start at the entry route, then act as the user would. A supported deep link (for example a notification URL) is fine; jumping to an internal route to skip the entry flow is not.
- Run the suite with tracing on against the unchanged snapshot.

**Produces** `<prototype>/baseline-evidence/`: copy `evidence/` there after this run, because the reporter wipes `evidence/` at the start of every run. Allowlist it as an addition.

**Gate** Each AC fails on its product assertion, or passes at baseline because the behaviour already exists (record which). Setup failures (server not started, missing dependency, selector typo) are not red evidence; fix them first.

## 5. UI plus stateful fake at the existing seam

**Do**
- Keep the current router, components, styles and request client. Add the proposed feature inside the snapshot, following the folder, naming, component and styling conventions in `ui-profile.md`.
- Replace the backend behind the existing fetch client, API route or proxy under an explicit prototype mode (see [web-mocks.md](references/web-mocks.md)). Match the real session and feature-flag response shapes so the shell picks the same navigation branch as production.
- The fake holds state across navigation and reload, applies commands atomically, and enforces modeled actor/scope checks at its boundary. Model delayed, failed, conflicting and duplicate responses only where the PRD needs them.
- Test-only seed/reset/role endpoints fail closed outside prototype mode. Prototype controls (scenario picker, role switch) live outside the product shell and are closed by default.
- Reuse the existing design direction. New visual choices need a recorded decision.

**Produces** feature code, fake backend module, `parity-allowlist.json` listing every changed or added path with a reason.

**Gate** The feature works manually from the entry route in prototype mode. Flag-on and flag-off sessions both render the intended shell.

## 6. Verify

**Do**
- Run the full Playwright suite with the reporter and tracing against an isolated mock server (never a shared or unknown one). Include the project's lint, type checks and unit tests.
- Check source parity:
  ```bash
  python3 scripts/snapshot.py verify --prototype /path/to/prototypes/PRD-007 \
    --allowlist /path/to/prototypes/PRD-007/parity-allowlist.json
  ```
- Check coverage:
  ```bash
  python3 scripts/check_coverage.py --contract coverage-contract.json \
    --results evidence/scenario-results.json --artifact-root /path/to/prototypes/PRD-007
  ```
- Open a few traces and screenshots yourself. The checker verifies records and files, not the truth of assertions.

**Produces** `evidence/scenario-results.json`, traces and screenshots under `evidence/`, parity report, coverage report.

**Gate** Suite green, `snapshot.py verify` exit 0 with narrow allowlist entries, `check_coverage.py` exit 0.

## 7. Handoff

**Do**
- Report: PRD id and prototype version, source commit and deployment comparison, exact commands run, AC counts (passed/failed/skipped/missing), screens required vs visited, allowlisted changes, mocked domains and unknowns, links to evidence.
- State the status honestly: **ready for product review**, **product review recorded** (actor, date, prototype_version), or **verified against the real backend**. Never promote one to the next without the matching evidence.
- After review, hand the ACs, fixtures and API/state discoveries to the implementation RFC. Real delivery is proven by integration tests and a live run, not by this suite. Retire the fake when the real backend lands.
- Optional: note elapsed time or model usage if measured; unknown is not zero.

**Produces** handoff note in the PRD or alongside it, with the evidence directory linked.

**Gate** The product owner can open the prototype and the evidence without asking you anything.

## Red flags, stop and report

- Guessing where the live UI lives, or applying your own stack defaults instead of the project's conventions.
- Editing an AC expectation so the test passes.
- Deep-linking past the entry screen to reach the feature.
- Allowlisting a whole directory, or any shell/style change without a reason.
- Writing or editing `scenario-results.json` by hand.
- Reusing one screenshot or trace for more than one AC.
- Claiming "approved" without a recorded review for this `prototype_version`.
- Calling the fake suite "done" or "production ready".
