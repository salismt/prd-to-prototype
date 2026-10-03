# Platform and mock decisions

Read when choosing the implementation seam or testing platform.

| Platform | Preserve | Mock seam | Runtime evidence |
|---|---|---|---|
| Web / website | Current router, layout, components, CSS, fonts/assets, HTTP clients | Existing proxy/fetch client/service adapter; MSW or in-process fake if it fits the app | Existing browser harness, such as Playwright/Cypress; traces, screenshots, actual screen assertions |
| React Native / Expo | Actual screens/navigation, theme, API hooks and native components | Existing client or repository dependency configured only for prototype builds | Existing native harness, such as Maestro/Detox, in emulator/simulator/device; recording/log + screenshots |
| Flutter | Actual widgets, navigation, theme and data-layer interfaces | Injected fake repository or transport in a dedicated prototype entry point/flavor | Flutter integration tests or project's native harness, emulator/device captures |
| SwiftUI / UIKit / Android Compose | Actual views, navigation, resources, session and lifecycle | Injected service/repository through a prototype build target/configuration | XCUITest / Android UI tests or existing harness; native recording/log + screenshots |
| Desktop | Actual application shell, menus, window behavior and data interfaces | Existing IPC/service adapter in isolated prototype mode | Existing desktop harness with actual window/UI assertions and captures |

These are options, not permission to install new frameworks. Use the stack and available tools already selected by the project. Browser-only verification of a responsive website establishes web behavior, not iOS/Android behavior. A native component preview establishes rendering only; navigation, keyboard, back gestures and persistence require the running app. If a required emulator/tool is unavailable, provide the artifacts and mark that runtime gate unverified.

## Stateful fake contract

Define only the behavior required by the PRD:

- Session: fixture identity, actor, scope, capabilities and actual feature-flag response shape.
- Seed/reset: deterministic scenario, session ID, empty/default/negative states; isolated between tests/reviewers.
- Read: current state, stable identifiers, permitted scope; delays/error/unknown only when selected.
- Command: modeled authority, validation, expected revision and retry key when required; reject before mutation, commit successful changes atomically.
- State inspection: test-only observable state/attempts for assertions, not hidden facts that the UI never presents.

Keep fixture-control requests separate from product requests. A neutral, closed developer drawer or test menu should seed the fixture, select the acting role and return to the natural entry flow. Disable/exclude it outside prototype mode. Use the existing product notification component to supply a synthetic feature entry rather than inventing a new homepage/navigation.

Example command behavior for a profile-edit feature:

1. A member saves an edited display name at revision 3.
2. The fake rejects a blank name and preserves the draft/old stored value.
3. Another client changes revision 3 to 4; a stale save receives a conflict and preserves input for review.
4. Retrying the identical request key returns the prior result, without a second change.
5. A viewer's forged save is rejected at the fake service boundary.

These are illustrative semantics. Apply them only when the feature's real product contract requires them.

## Connectivity and flags

A source UI may use server-side route guards, background sync, analytics, uploads or native SDKs outside the main data client. Inspect those paths before running synthetic workflows. Use the existing test mechanism or a scoped prototype configuration to prevent real side effects. Do not turn off protections in a deployed environment to make a prototype work.

Match the actual flag-on and flag-off session shapes and role combinations. If the shell branches on a session endpoint, a missing mock response can silently select the wrong navigation while every feature assertion passes. Add a shell/flag journey and source parity checks to catch that error.

## New applications

There may be no deployed UI to copy. Pin the current starter/design selection, keep the shell stable through the prototype, and state that the baseline is a starter. Write acceptance journeys before feature implementation. A missing starter or unselected visual direction is a product decision, not a reason to claim imaginary existing parity.
