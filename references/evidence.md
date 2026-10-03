# Evidence contract

Three layers, checked separately: source parity (`snapshot.py verify`), acceptance coverage (`check_coverage.py`), and recorded human review. None of them substitutes for another, and none is a backend delivery claim.

## Baseline snapshot

`scripts/snapshot.py` needs Python 3.9+ and Git, nothing else.

```bash
python3 scripts/snapshot.py create --repo /path/to/source --destination /path/to/prototypes/PRD-007 \
  --remote origin --fetch --ref origin/main --path frontend --path packages/ui --path package.json
```

It copies committed files for the selected paths at the resolved commit, keeps their repository-relative layout, and writes a manifest with commit, paths, fetch status and per-file hashes. It refuses an existing destination, unresolved submodules and links that escape the source. Use `--offline-reason` instead of `--fetch` when the remote is deliberately not fetched. It does not scan for secrets or prove what is deployed; record deployment provenance in the PRD.

Why copy rather than branch: prototypes often live outside the product repository (a `prototypes/PRD-007` folder next to the PRD), and a pinned copy with a hash manifest is reviewable and cannot silently mutate the source checkout. When the prototype stays inside the product repo, `git worktree add <dir> <commit>` is an acceptable baseline; review `git diff <commit> --name-status` against the same allowlist rules below.

### Parity allowlist

```json
{
  "changes": [
    {"path": "frontend/src/app/layout.tsx", "reason": "Prototype-only closed scenario drawer"}
  ],
  "additions": [
    {"path": "frontend/src/features/profile-revamp", "reason": "Proposed PRD UI and fake adapter"},
    {"path": "evidence", "reason": "Reporter output, traces and screenshots"},
    {"path": "coverage-contract.json", "reason": "PRD acceptance mapping"}
  ]
}
```

Changed or deleted baseline files need an exact path each. An addition may name a new directory and covers its descendants, but cannot overlap a baseline path. Dependencies and build output are ignored only for addition discovery. `verify` lists changes, missing and added files, used exceptions and anything unexplained; exit 0 only when everything is explained. An allowlist is an explanation, not approval. Do not allowlist the whole app.

## Coverage: contract and results

The contract is written in step 2; the results are written by the test runner in step 6.

**`coverage-contract.json`**

| Field | Meaning |
|---|---|
| `prd_id` | PRD identifier |
| `entry_screens` | Screens a journey may start on |
| `screens` | All screen ids in scope |
| `acceptance[]` | `{id, screens}`: AC id and the screens it must visit |

AC ids are any unique non-empty strings; `AC-01` is a convention, not a required pattern.

**`scenario-results.json`**

| Field | Meaning |
|---|---|
| `prd_id` | Must match the contract |
| `prototype_version` | Commit or tag of the prototype that ran |
| `run_started_at` | ISO-8601 with timezone; artifacts older than this are rejected |
| `runner` | `{name, version}` of the test runner that produced the file |
| `results[]` | One final row per AC: `id`, `status`, `entry_screen`, `visited_screens`, `recording`, `screenshots` |
| `review` | Optional: `status`, `actor`, `prototype_version`, `evidence` |

Artifact paths are relative to `--artifact-root`, must stay inside it, and must be real files: `recording` is a Playwright trace `.zip` or a `.webm` video, `screenshots` are PNG or JPEG. File signatures are checked, so an empty or renamed file fails. An artifact may belong to one AC only.

```bash
python3 scripts/check_coverage.py --contract coverage-contract.json \
  --results evidence/scenario-results.json --artifact-root /path/to/prototypes/PRD-007 \
  --output evidence/coverage.json
```

Exit codes: `0` every AC has one passing result whose visited screens cover the contract and whose artifacts exist and are fresh; `1` the gate is incomplete (a failed, skipped, missing or duplicate AC, an unvisited screen, a bad artifact, or a malformed row, which fails that AC only); `2` the input file or invocation itself is malformed.

The `review` block is reported separately. An `approved` review must name the current `prototype_version`; a green suite never becomes approval on its own.

## Producing results: adapter first

Use the [Playwright adapter](../adapters/playwright/README.md). It gives you `expectScreen(...)`, which asserts the screen is visible and only then records the visit with a screenshot, and a reporter that writes `scenario-results.json` from the final attempt per AC (AC id taken from the `@AC-01` test tag) and copies trace and screenshots under `evidence/`.

If the project already runs Cypress or another runner, write an adapter that emits the same schema. Rules it must follow:

- One final row per AC; keep retries and failures in the runner's own report.
- Record a screen only after a visible assertion on it passes. Route lists, screen declarations and screenshot directories are not visits.
- Every test records independently, including when the helper is shared across files. A module-level hook imported once may attach to the first file only.
- Produce real recordings and screenshots from the run; never copy, reuse or hand-write them.

The checker validates records and files. It cannot read a trace, prove an assertion ran, or judge design quality. Open representative traces and screenshots yourself before handoff.

## Handoff record

Keep it short and link evidence:

- PRD id, prototype version, source commit, deployment comparison or why unavailable.
- Allowlisted changes and the parity result; shell states inspected (flag-on/off, roles).
- AC totals (passed, failed, skipped, missing) and required vs visited screens.
- Exact commands, run date, paths to reporter output, traces and screenshots.
- Mocked domains, unresolved rules, anything not verifiable in the prototype.
- Review status with actor, date and `prototype_version` when recorded; next owner.
- Optional: elapsed time or model usage if measured.
