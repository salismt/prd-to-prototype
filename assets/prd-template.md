# PRD-[ID] — [Feature]

Status: Draft / ready for prototype review / reviewed (record the actual state).
Owner: [product owner]. Platform: [web/native/desktop]. Version/date: [version/date].
Baseline: [source commit, starter if new app, deployment evidence or limitation].
Design decision: [existing direction and any explicitly authorized changes].
Dependencies: [existing features/API contracts].

## Problem and intended outcome

[Who encounters what problem, normal entry point, observable successful outcome, scope exclusions.]

## Actors and permissions

[Which actor can view/mutate each relevant state; demo role selection is not authentication.]

## States and transitions

| State | Action | Actor / guard | Result | Error / retry behavior |
|---|---|---|---|---|
| [state] | [named action] | [permission and data] | [new state/side effect] | [preserved state/input] |

## Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-01 | [observable behavior] | AC-01 |

## Screens and entry flow

| Screen | Existing / proposed route or native view | Entry action | States |
|---|---|---|---|
| S1 | [normal home/notification entry] | [start] | [loading/empty/data] |
| S2 | [feature] | [action from S1] | [editing/success/validation/retry] |

Preserved shell: [navbar/sidebar/tabs, home, topbar, background/tokens, session/flag branches].
Authorized deltas: [specific changes or none]. Prototype controls: [separate closed control].

## Data and mocked backend contract

[Identifiers/versions, API or repository seam, deterministic fixtures, modeled guards, failure cases,
side effects, isolation/reset and unknown domain rules. Do not prescribe a production architecture.]

## Acceptance scenarios

| ID | Given | When from normal entry | Then: UI and resulting state | FR / screens |
|---|---|---|---|---|
| AC-01 | [fixture, actor and flag] | [home → exact action → save] | [visible outcome + stored state] | FR-01 / S1 S2 |

[Add applicable permissions, missing/stale/empty/error/retry/concurrency and platform cases.
Keep IDs stable; derive expected results from product intent.]

## Design and verification evidence

[Editable source assets, regenerated static exports, separate runtime screenshots/recordings,
red-baseline results, green results, actual AC/screen coverage and source parity.]

## Rollout and implementation handoff

[Compatibility questions, real API/integration validation required, rollout/rollback,
product review record by artifact/version, next owner. Prototype success does not authorize deployment.]
