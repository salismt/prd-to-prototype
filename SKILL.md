---
name: prd-to-prototype
description: Turn a PRD for a new web, website, desktop, or mobile UI feature into an acceptance-tested prototype using the current application and a stateful mocked backend. Use for PRD-driven feature discovery and prototype review before backend implementation; not for backend-only work or production deployment.
license: MIT
metadata:
  author: salismt
  version: "1.0.0"
---

# PRD to Prototype

Make the intended feature concrete enough to review before building its backend:

**PRD acceptance examples → failing UI journeys → current UI + stateful fake → passing journeys and parity evidence → product-owner review → implementation handoff.**

The prototype is the existing application running against a fake backend. Passing mocked tests demonstrates proposed behavior, not production readiness or actual external-service results.

## Scope and starting point

Read the project's applicable instructions, PRD, and affected UI/API code. Identify the product owner, target platform, feature scope, existing design direction, normal user entry point, and review/build commands. Preserve the user's choices and authorization. Ask only for missing decisions that materially change the feature; continue independent work while an answer is pending.

For a new application, use the current starter or selected design baseline. If neither exists, establish the shell and design direction explicitly; do not invent a previously shipped baseline. For changes to an existing feature, use its current code and runtime as evidence of present behavior, rather than an older PRD or prototype.

Use these resources as needed:

- [PRD template](assets/prd-template.md) when drafting or repairing the product contract.
- [Platform and mock guidance](references/platforms-and-mocks.md) for choosing the existing API seam and the web/native test harness.
- [Evidence contract](references/evidence.md) for source parity, coverage adapters and handoff records.
- [Contract example](assets/coverage-contract.example.json) and [result example](assets/scenario-results.example.json) for the coverage checker. They are synthetic examples, not evidence of a real run.

## 1. Fix the acceptance contract first

Keep stable requirement, acceptance and screen IDs. Each acceptance row specifies:

- Given: fixture, actor/permissions, feature flags and starting state.
- When: normal home, received notification or supported entry flow, followed by named UI actions.
- Then: observable UI outcome and relevant resulting state or side effect.
- Required screens and linked requirements.

Include the feature's meaningful negative cases: unavailable or stale information, validation, role boundaries, empty/error/retry states, duplicates, interrupted work and concurrent changes where relevant. Distinguish permission policy from selecting a demonstrated role. Define the backend behavior being simulated; unresolved domain rules remain explicit unknowns or blocked cases.

Do not change acceptance expectations merely to make the UI pass. Classify a discrepancy as a requirement clarification, implementation defect or new scope; reconcile it with the owning PRD and record the decision.

## 2. Fetch and copy a fresh application baseline for this PRD

Fetch the source repository's configured remote, determine the appropriate source commit, and copy the UI source, assets, shared packages, lockfiles and build configuration needed to run it into an isolated PRD prototype. Do not modify the source checkout or overwrite an earlier prototype. Never substitute an earlier PRD's fake app for a fresh source copy.

If the deployed commit is known, use it when reproducing the live baseline. If the user wants latest code or the deployment is unavailable, pin the selected source commit and state the difference. A successful source fetch is not proof of deployment. Offline or inaccessible source is a recorded limitation, not silently fresh evidence.

The optional standard-library helper creates a committed-source snapshot without copying uncommitted files:

```bash
python3 scripts/snapshot.py create --repo /path/to/app --ref origin/main \
  --remote origin --fetch --path frontend --destination /path/to/prototypes/PRD-007
```

Run scripts relative to this skill's directory or resolve their absolute paths; output paths belong to the target project. Select actual project paths and remote/ref; the example is not a prescribed framework layout. For monorepos, select required shared packages and workspace configuration too. For an explicitly requested working-tree baseline, preserve and identify its changes separately: this helper snapshots commits only.

Record commit, deployment evidence if available, platform, design/flag/session state and file hashes. Preserve navigation, home, background, typography, tokens and shared components unless the PRD/user explicitly changes them. If the feature changes these areas, record the intended delta and verify unaffected surfaces. Prototype controls live outside the product composition and are closed by default.

## 3. Write and run the failing UI journeys before feature changes

Use the project's real UI harness. Prefer one independently runnable scenario per AC ID; group additional journey coverage when needed. Seed data before interaction, then start where the user would start. A supported notification deep link is valid; jumping directly to an internal target to bypass the entry flow is not.

Record the initial assertion failure and its trace or equivalent native recording. Toolchain failures, missing credentials and a server that never started are setup blockers, not red acceptance evidence. Existing behavior that already satisfies an AC may pass at baseline; record that honestly instead of manufacturing a failure.

Trace asserted screen visits during execution. A screen declaration, route list or screenshot directory alone does not establish coverage. Record every scenario independently, including when its common helper is shared across test files.

## 4. Implement the proposed UI with a stateful fake at the existing seam

Keep current routing, components, styles, request clients and native data repositories. Extend the in-snapshot app for the PRD's proposed feature. Reproduce the actual session/feature-flag contract so the intended navigation and permissions branch renders. Check relevant flag-on/off branches instead of assuming a default session is equivalent.

Use an explicit prototype/test mode to replace the backend behind its HTTP client, proxy, repository or service interface. Block accidental live mutations. Test-only seed, role and state controls must be absent or fail closed outside prototype mode. Do not port auth bypasses or mock control endpoints into production.

Use deterministic, synthetic fixtures and per-test/per-reviewer state isolation. State survives normal navigation and refresh for the demonstrated session. Apply transitions atomically in the fake; enforce modeled actor/scope checks at its command boundary as well as in the UI. Share domain transition definitions where practical, so button enablement and fake guards agree. Exercise idempotency and stale-version handling when the PRD calls for them.

A role picker changes test identity; it is not authentication evidence. Simulate delayed, failed, unknown and conflicting responses deliberately. Clearly identify fake external results. Implement only enough backend behavior to exercise the PRD, rather than inventing a production backend architecture.

Provide a scenario picker or platform-appropriate developer control that seeds an AC's fixture and returns to its entry point. Fixture selection is not automated playback and does not record product approval. Reuse the selected design direction. New visual choices require a concrete review only if the user has not already authorized or selected them.

## 5. Verify the whole in-scope flow and preserve parity

Run the acceptance suite with recording enabled and an isolated mock server/test runtime. Avoid reusing an unknown server. Include the feature's positive and negative journeys, required screens, and applicable responsive/native accessibility states. Adapt commands to the project instead of requiring a browser test for native UI.

Verify source parity against the snapshot, listing specific prototype changes and additions with reasons:

```bash
python3 scripts/snapshot.py verify --prototype /path/to/prototypes/PRD-007 \
  --allowlist /path/to/prototypes/PRD-007/parity-allowlist.json
```

Do not allowlist the entire app or unexplained shell/style changes. Source hashes alone do not prove runtime parity: inspect the actual home/navigation, relevant flag branches, backgrounds and platform layout. Keep scenario controls out of ordinary feature screenshots.

For web, keep editable, source-derived HTML designs in the PRD's assets and regenerate static PNGs from them; copy styles, fonts and images so the designs render without broken assets. Do not recreate the shell with custom CSS. For native UI, keep editable native component/view sources or the selected design artifact; an HTML approximation is not native evidence. Keep static design exports distinct from screenshots captured by a running application.

Run appropriate project lint/type checks, unit tests and builds. Check critical assumptions early, run focused checks while iterating, then the complete PRD suite for handoff. Broaden regression checks when the change or project requires them; avoid repeating unrelated full suites without a new reason.

Export actual test results to the evidence contract, then check them:

```bash
python3 scripts/check_coverage.py --contract /path/to/coverage-contract.json \
  --results /path/to/scenario-results.json --artifact-root /path/to/prototype
```

Every AC needs one final passing result with its required screens actually visited and nonempty referenced recording/screenshots. Failed, skipped, missing or duplicate results do not count as complete. The checker validates records and artifact presence, not the truth of the assertions or the contents of a recording; inspect the underlying runner report. Never hand-author successful evidence to satisfy the checker.

## 6. Deliver a reviewable result, then hand off implementation

Report artifact links, source/deployment provenance, exact commands and outcomes, AC/screen coverage, runtime versus static evidence, mock limitations, unresolved decisions and next owner. Record elapsed/model usage when available; unavailable values are unknown, not zero.

Distinguish **ready for product review**, **product review recorded**, and **verified against the real backend**. A green fake suite is ready for review. Record an authorized review against the specific prototype version; do not manufacture approval or ask again when existing authorization covers the artifact. If review is pending, deliver the concrete prototype and keep that gate open.

After review, pass acceptance scenarios and data/state/API discoveries into the project's RFC or implementation process. Preserve acceptance meaning when replacing the fake with real services. Prove delivery using real integration/backend tests and a live local app run. Treat the fake as a prototype artifact, not a long-lived parallel implementation that quietly diverges during development.
