#!/usr/bin/env python3
"""Check actual PRD scenario records and referenced artifacts; not assertion truth."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys


def strings(value, label, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(s, str) or not s.strip() for s in value) or len(value) != len(set(value)):
        raise ValueError(label + " must be an array of unique nonempty strings")
    return value


def required_string(obj, key):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(key + " must be a nonempty string")
    return value


def check(contract, evidence, root):
    if not isinstance(contract, dict) or not isinstance(evidence, dict):
        raise ValueError("Contract and results must be objects")
    prd = required_string(contract, "prd_id")
    if required_string(evidence, "prd_id") != prd:
        raise ValueError("PRD identifiers do not match")
    version = required_string(evidence, "prototype_version")
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
        if not re.fullmatch(r"AC-\d{2,}", ident) or ident in expected:
            raise ValueError("Invalid or duplicate AC identifier: " + ident)
        required = set(strings(row.get("screens"), ident + " screens"))
        if not required <= screens:
            raise ValueError("Undeclared screen in " + ident)
        expected[ident] = required
    ids = []
    for r in results:
        if not isinstance(r, dict):
            raise ValueError("Result rows must be objects")
        ids.append(required_string(r, "id"))
    duplicates = sorted(k for k, n in Counter(ids).items() if n > 1)
    unknown = sorted(set(ids) - set(expected))
    missing = sorted(set(expected) - set(ids))
    failures, passed, visited = [], [], set()

    def artifact(value, ident):
        if not isinstance(value, str) or not value.strip() or Path(value).is_absolute() or ".." in Path(value).parts:
            failures.append(ident + ": invalid artifact path")
            return
        p = (root / value).resolve()
        if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size == 0:
            failures.append(ident + ": missing, empty or out-of-root artifact: " + value)

    for r in results:
        ident = r["id"]
        if ident not in expected or ident in duplicates:
            continue
        before = len(failures)
        if r.get("status") != "passed":
            failures.append(ident + ": final result is " + str(r.get("status", "missing")))
            continue
        actual = set(strings(r.get("visited_screens"), ident + " visited_screens"))
        entry = required_string(r, "entry_screen")
        if entry not in entries or entry not in actual:
            failures.append(ident + ": did not start at a declared user entry")
        if not actual <= screens:
            failures.append(ident + ": undeclared visited screen")
        if not expected[ident] <= actual:
            failures.append(ident + ": required screens not visited: " + ", ".join(sorted(expected[ident] - actual)))
        artifact(r.get("recording"), ident)
        for p in strings(r.get("screenshots"), ident + " screenshots"):
            artifact(p, ident)
        if len(failures) == before:
            passed.append(ident)
            visited.update(actual)
    review = evidence.get("review", {"status": "pending"})
    if not isinstance(review, dict) or review.get("status") not in {"pending", "approved", "changes-requested"}:
        raise ValueError("Invalid review record")
    if review["status"] == "approved":
        required_string(review, "actor")
        required_string(review, "evidence")
        if review.get("prototype_version") != version:
            raise ValueError("Review approval references a different prototype version")
    unvisited = sorted(screens - visited)
    return {"prd_id": prd, "prototype_version": version, "acceptance_total": len(expected), "passed_ids": sorted(passed),
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
