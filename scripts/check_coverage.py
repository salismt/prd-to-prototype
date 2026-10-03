#!/usr/bin/env python3
"""Check actual PRD scenario records and artifact plausibility (type, freshness, reuse); not assertion truth."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys

SIGNATURES = {".zip": b"PK\x03\x04", ".webm": b"\x1a\x45\xdf\xa3", ".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff"}
RECORDING, SCREENSHOT = {".zip", ".webm"}, {".png", ".jpg", ".jpeg"}
TOLERANCE = 2  # seconds of mtime slack against run_started_at


def strings(value, label, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(s, str) or not s.strip() for s in value) or len(value) != len(set(value)):
        raise ValueError(label + " must be an array of unique nonempty strings")
    return value


def required_string(obj, key):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(key + " must be a nonempty string")
    return value


def run_start(evidence):
    value = required_string(evidence, "run_started_at")
    try:
        started = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        raise ValueError("run_started_at must be an ISO-8601 timestamp")
    if started.tzinfo is None:
        raise ValueError("run_started_at must include a timezone")
    return started.timestamp()


def check(contract, evidence, root):
    if not isinstance(contract, dict) or not isinstance(evidence, dict):
        raise ValueError("Contract and results must be objects")
    prd = required_string(contract, "prd_id")
    if required_string(evidence, "prd_id") != prd:
        raise ValueError("PRD identifiers do not match")
    version = required_string(evidence, "prototype_version")
    started = run_start(evidence)
    runner = evidence.get("runner")
    if not isinstance(runner, dict):
        raise ValueError("runner must be an object with name and version")
    runner = {"name": required_string(runner, "name"), "version": required_string(runner, "version")}
    screens = set(strings(contract.get("screens"), "screens"))
    entries = set(strings(contract.get("entry_screens"), "entry_screens"))
    if not entries <= screens:
        raise ValueError("Entry screens must be declared screens")
    rows, results = contract.get("acceptance"), evidence.get("results")
    if not isinstance(rows, list) or not rows or not isinstance(results, list):
        raise ValueError("Acceptance must be nonempty and results must be an array")
    expected = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Acceptance rows must be objects")
        ident = required_string(row, "id")
        if ident in expected:
            raise ValueError("Duplicate AC identifier: " + ident)
        required = set(strings(row.get("screens"), ident + " screens"))
        if not required <= screens:
            raise ValueError("Undeclared screen in " + ident)
        expected[ident] = required
    failures, ids = [], []
    for i, r in enumerate(results):
        try:
            ids.append(required_string(r if isinstance(r, dict) else {}, "id"))
        except ValueError as e:
            failures.append("results[%d]: %s" % (i, e))
    duplicates = sorted(k for k, n in Counter(ids).items() if n > 1)
    unknown = sorted(set(ids) - set(expected))
    missing = sorted(set(expected) - set(ids))
    users, ok = {}, {}

    def artifact(value, ident, kinds, label):
        if not isinstance(value, str) or not value.strip() or Path(value).is_absolute() or ".." in Path(value).parts:
            failures.append(ident + ": invalid artifact path")
            return
        p = (root / value).resolve()
        if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size == 0:
            failures.append(ident + ": missing, empty or out-of-root artifact: " + value)
            return
        ext = p.suffix.lower()
        with p.open("rb") as f:
            head = f.read(8)
        if ext not in kinds:
            failures.append(ident + ": " + label + " must be one of " + ", ".join(sorted(kinds)) + ": " + value)
        elif not head.startswith(SIGNATURES[ext]):
            failures.append(ident + ": artifact content does not match its extension: " + value)
        if p.stat().st_mtime < started - TOLERANCE:
            failures.append(ident + ": artifact predates this run: " + value)
        users.setdefault(str(p), []).append(ident)

    for r in results:
        ident = r.get("id") if isinstance(r, dict) else None
        if ident not in expected or ident in duplicates:
            continue
        before = len(failures)
        try:
            if r.get("status") != "passed":
                raise ValueError("final result is " + str(r.get("status", "missing")))
            actual = set(strings(r.get("visited_screens"), "visited_screens"))
            entry = required_string(r, "entry_screen")
            if entry not in entries or entry not in actual:
                failures.append(ident + ": did not start at a declared user entry")
            if not actual <= screens:
                failures.append(ident + ": undeclared visited screen")
            if not expected[ident] <= actual:
                failures.append(ident + ": required screens not visited: " + ", ".join(sorted(expected[ident] - actual)))
            artifact(r.get("recording"), ident, RECORDING, "recording")
            for p in strings(r.get("screenshots"), "screenshots"):
                artifact(p, ident, SCREENSHOT, "screenshot")
        except ValueError as e:
            failures.append(ident + ": " + str(e))
        if len(failures) == before:
            ok[ident] = actual
    for path, idents in sorted(users.items()):
        if len(idents) > 1:
            for ident in idents:
                failures.append(ident + ": artifact shared with " + ", ".join(sorted(set(idents) - {ident})) + ": " + str(Path(path).relative_to(root)))
                ok.pop(ident, None)
    review = evidence.get("review", {"status": "pending"})
    if not isinstance(review, dict) or review.get("status") not in {"pending", "approved", "changes-requested"}:
        raise ValueError("Invalid review record")
    if review["status"] == "approved":
        required_string(review, "actor")
        required_string(review, "evidence")
        if review.get("prototype_version") != version:
            raise ValueError("Review approval references a different prototype version")
    visited = set().union(*ok.values()) if ok else set()
    unvisited = sorted(screens - visited)
    return {"prd_id": prd, "prototype_version": version, "run_started_at": evidence["run_started_at"], "runner": runner,
            "acceptance_total": len(expected), "passed_ids": sorted(ok),
            "missing_ids": missing, "duplicate_ids": duplicates, "unknown_ids": unknown,
            "screen_total": len(screens), "visited_screens": sorted(visited), "unvisited_screens": unvisited,
            "failures": failures, "review_status": review["status"],
            "coverage_passed": not (missing or duplicates or unknown or unvisited or failures)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        root = Path(args.artifact_root).resolve()
        if not root.is_dir():
            raise ValueError("Artifact root must be a directory")
        report = check(json.loads(Path(args.contract).read_text()), json.loads(Path(args.results).read_text()), root)
        text = json.dumps(report, indent=2) + "\n"
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text)
        print(text, end="")
        return 0 if report["coverage_passed"] else 1
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as e:
        print("error: " + str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
