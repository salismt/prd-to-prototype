# PRD-DEMO-001 — Edit display name on profile

Status: ready for prototype review (synthetic demo PRD shipped with the skill).
Owner: skill maintainers. Platform: web. Version/date: demo, no release.
Baseline: the `web-demo` shell in this directory (nav + home). No deployment exists; this is a self-contained example.
Design decision: keep the existing shell and tokens; the profile form reuses them. No new visual direction.
Dependencies: `/api/profile` and `/api/session` as served by the stateful fake in `server.js`.

## Problem and intended outcome

A signed-in user wants to change the display name shown on the home screen. They start at Home, open Profile from
the nav, edit the name and save. The new name is visible immediately and after a reload. Out of scope: avatars,
username/handle changes, audit history.

## Actors and permissions

| Actor | View profile | Save display name |
|---|---|---|
| editor | yes | yes |
| viewer | yes | no — rejected by the backend, not merely hidden in the UI |

The demo selects the actor through the test-only reset endpoint; that is fixture selection, not authentication.

## States and transitions

| State | Action | Actor / guard | Result | Error / retry behavior |
|---|---|---|---|---|
| profile(rev n) | Save name | editor, nonblank name, submitted rev == n | profile(rev n+1), success message | — |
| profile(rev n) | Save name | viewer | unchanged | 403, alert shown, draft kept |
| profile(rev n) | Save blank | editor | unchanged | 400, alert shown, stored name kept |
| profile(rev n) | Save with rev m != n | editor | unchanged | 409, alert names the conflict, draft kept in the input |

## Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-01 | An editor can rename and the name persists across reload and on Home | AC-01 |
| FR-02 | A blank name is rejected and the stored name is unchanged | AC-02 |
| FR-03 | A stale revision is rejected and the user's draft is preserved | AC-03 |
| FR-04 | A viewer's save is rejected at the command boundary | AC-04 |

## Screens and entry flow

| Screen | Existing / proposed route or native view | Entry action | States |
|---|---|---|---|
| S1 | `#/` Home (existing) | start | data |
| S2 | `#/profile` Profile (proposed) | nav link "Profile" from S1 | editing / success / validation / conflict / forbidden |

Preserved shell: top nav, home greeting, typography. Authorized deltas: none.
Prototype controls: `POST /__test/reset`, present only when `PROTOTYPE_MODE=1`.

## Data and mocked backend contract

Seed: `{ profile: { name: "Ada Lovelace", revision: 1 }, actor: "editor" }`. `PUT /api/profile` takes
`{ name, revision }` and applies the guards above atomically in memory. `POST /__test/reset` restores the seed and
accepts `{ actor, profile }` overrides. One server process holds one state, so scenarios run serially.

## Acceptance scenarios

| ID | Given | When from normal entry | Then: UI and resulting state | FR / screens |
|---|---|---|---|---|
| AC-01 | seed, editor | Home → Profile → type "Grace Hopper" → Save → reload → Home | success status; profile and home show "Grace Hopper" | FR-01 / S1 S2 |
| AC-02 | seed, editor | Home → Profile → type blanks → Save → reload | alert "Display name cannot be blank."; stored name still "Ada Lovelace" | FR-02 / S1 S2 |
| AC-03 | seed, editor; another editor saves rev 1 → 2 before the user saves | Home → Profile → type "Draft Name" → Save | conflict alert; input still holds "Draft Name"; reload shows the other editor's name | FR-03 / S1 S2 |
| AC-04 | seed, viewer | Home → Profile → type a name → Save | alert "Viewers cannot edit the display name."; `/api/profile` unchanged | FR-04 / S1 S2 |

## Design and verification evidence

Runtime evidence is produced by `npm test` into `evidence/` (trace + screenshots per AC and
`scenario-results.json`) and gated by `npm run check`. No static design exports exist for this demo.

## Rollout and implementation handoff

Not applicable: this PRD exists to exercise the adapter and checker. A green run here is not a delivery claim.
