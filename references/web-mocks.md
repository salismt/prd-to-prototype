# Web mock seams

Read when deciding where the fake backend plugs in. The rule: preserve the router, layout, components, CSS, fonts and HTTP client; replace only what sits behind the app's existing API boundary.

| Seam | When it fits | Notes |
|---|---|---|
| Existing fetch/HTTP client (`apiClient`, `axios` instance, generated SDK) | The app routes all requests through one module | Swap the base URL or inject a fake transport in prototype mode. Smallest blast radius. |
| Framework API routes / BFF handlers (Next.js `app/api`, Remix loaders, SvelteKit `+server`) | The frontend already calls its own server routes | Serve the fake from the same routes. Keeps request shapes identical. |
| Dev-server proxy (`vite.config` `server.proxy`, `next.config` `rewrites`) | The app talks to a separate backend origin | Point the proxy at an in-process fake server started by the test runner. |
| MSW (service worker or Node) | The project already uses MSW, or request shapes are the main risk | Handlers hold state in a module; reset per test. Do not add MSW to a project only for this. |
| In-process fake module | Small app, few endpoints, no proxy layer | Import the fake behind the client interface; still gate it on prototype mode. |

Pick the seam the project already has. Do not install a new framework or mock library when an existing seam works.

## Prototype mode

- One explicit switch (`PROTOTYPE_MODE=1`, a `.env.prototype`, or a build flag). Everything below depends on it.
- Test-only endpoints (`/__test/reset`, `/__test/seed`, `/__test/role`) return 404 or are not registered when the switch is off. Verify this once with a request in normal mode.
- Block real mutations: analytics, uploads, third-party SDKs, background sync. Inspect routes that bypass the main client (server-side guards, middleware) before assuming the fake covers them.
- Never weaken a deployed environment to make a prototype work.

## Session and flag parity

If the shell branches on a session or feature-flag endpoint, the fake must return the same shape, including the fields the UI never shows. A missing or guessed response can select the wrong navigation branch while every feature assertion passes. Cover it:

- Copy a real response (de-identified) for flag-on and flag-off, and for each demonstrated role.
- Add one journey per shell branch that asserts the navigation the user actually sees.
- Treat a role picker as test identity, not authentication.

## Stateful fake contract

Define only what the PRD needs:

- **Session**: identity, actor, scope, capabilities, flag response shape.
- **Seed/reset**: deterministic fixtures per scenario, isolated per test and per reviewer (a session id or storage key).
- **Read**: current state with stable ids and permitted scope. Delays, errors and unknowns only when a scenario selects them.
- **Command**: validate, check actor/scope, check expected revision and idempotency key where the PRD requires, reject before mutation, commit atomically.
- **Inspection**: test-only read of state and attempt counts for assertions. Never present facts the UI does not show as if they were UI.

State survives navigation and reload within the demonstrated session. Share transition rules between UI enablement and fake guards where practical so a disabled button and a rejected command agree.

### Example: profile edit

1. A member saves an edited display name at revision 3; the fake stores it as revision 4.
2. A blank name is rejected; the draft and stored value are both preserved.
3. Another client moves revision 3 to 4; a stale save gets a conflict and the input is kept for review.
4. Retrying with the same idempotency key returns the first result without a second change.
5. A viewer's forged save is rejected at the fake boundary, not only hidden in the UI.

These are illustrative. Apply them only when the feature's product contract calls for them.

## Prototype controls

A closed drawer or dev menu, rendered outside the product layout, that seeds a scenario, selects the acting role and returns to the entry route. It is absent outside prototype mode. Fixture selection is not playback and records no approval. Keep it out of feature screenshots.

Use the product's existing notification or inbox component for a synthetic feature entry rather than inventing a new homepage.

## New applications

With no deployed UI to copy, pin the chosen starter and design direction, keep the shell stable through the prototype, and say the baseline is a starter. Write the acceptance journeys before the feature. A missing visual direction is a product decision, not grounds to claim parity with something that never existed.
