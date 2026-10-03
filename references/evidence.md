# Source, coverage and review evidence

## Baseline helper

`scripts/snapshot.py` needs Python 3.9+ and Git. It has no Python package dependencies.

```bash
python3 scripts/snapshot.py create --repo /path/to/source --destination /path/to/new-prototype \
  --remote origin --fetch --ref origin/main --path frontend --path packages/ui --path package.json
```

It snapshots committed, selected paths at an immutable resolved commit and preserves their repository-relative paths. Start the copied app from its corresponding directory. Include lockfiles, workspace config and packages needed to build. Git submodules are refused: resolve/copy and identify them explicitly rather than recording an empty directory. For an intentionally offline snapshot, use `--offline-reason` instead of `--fetch`. The source checkout is unchanged; no existing destination is overwritten. Tracked credentials still require source inspection before copying; this is not a secret scanner.

The manifest captures file hashes, mode/type, commit, selected paths and whether fetch happened. It does not verify deployment. Record deployment provenance independently in the PRD/handoff, including an unavailable comparison.

Example parity allowlist, with exact paths and reasons:

```json
{
  "changes": [
    {"path": "frontend/src/app/layout.tsx", "reason": "Prototype-only closed scenario drawer"}
  ],
  "additions": [
    {"path": "frontend/src/features/profile-revamp", "reason": "Proposed PRD UI and fixture adapter"},
    {"path": "evidence", "reason": "Runner reports and recording artifacts"},
    {"path": "coverage-contract.json", "reason": "PRD acceptance mapping"}
  ]
}
```

Changed/deleted baseline files need exact-path exceptions. Addition entries may name a new feature directory and include its descendants; they cannot overlap a baseline path. Generated dependencies/build output are ignored only for addition discovery; tracked baseline files are always checked. `verify` reports changes, missing/added files, used exceptions and unexpected differences. Use narrow exceptions and inspect the diff; an allowlist is an explanation, not product approval.

## Coverage adapter

The JSON shape is illustrated under `assets/`. Build an adapter around the project's runner: emit a final result per AC, preserve retries/failures in its recording/report, and record the entry plus screens after a visible assertion succeeds. Each passed result references a trace/recording/log and at least one runtime screenshot. Paths are relative to `--artifact-root`, remain inside it and point to nonempty files. A native runner log may be the recording when the harness cannot produce video; name the limitation in the handoff.

Do not infer visits from route lists or declarative screen annotations. Shared helpers must record every test independently; a module-level hook imported once may only attach to the first test file. The checker compares actual records with the PRD mapping and checks artifact presence. It cannot inspect the content of a trace, prove assertions executed, verify that screenshots were captured during that run, or establish design quality. Inspect the runner report and representative recordings/screenshots.

Contract fields: `prd_id`, `entry_screens`, `screens`, and `acceptance` rows with `id` and required `screens`. Result fields: matching `prd_id`, `prototype_version`, and `results` with `id`, `status`, `entry_screen`, `visited_screens`, `recording`, `screenshots`. Optional `review` has `status`, `actor`, `prototype_version` and `evidence`; an approved record must refer to the current version. The checker reports review status separately; it never turns a green suite into approval.

```bash
python3 scripts/check_coverage.py --contract contract.json --results results.json \
  --artifact-root /path/to/prototype --output /path/to/prototype/evidence/coverage.json
```

Exit 0: all AC/screen/recorded-artifact checks pass. Exit 1: coverage/evidence gate is incomplete. Exit 2: malformed input or tool invocation. None is a backend delivery claim.

## Handoff record

Keep it concise and link evidence rather than copying the PRD:

- Feature/PRD/version; current source commit and deployed/source comparison.
- Authorized UI changes; shell parity results and inspected runtime states.
- AC totals: passed, failed, skipped and missing; required/actually visited screens.
- Commands, dates, runner reports, recordings and runtime captures; separate static design sources/exports.
- Mocked domains, unresolved rules and unavailable platform/provider validation.
- Review status with actor, artifact/version and scope when recorded; next implementation owner/gate.
- Measured elapsed/model usage if available, otherwise unknown.

Maintain separate layers: source parity, mocked runtime behavior, static design exports, recorded human review, real integration tests and production health. Evidence from one layer cannot substitute for another.
