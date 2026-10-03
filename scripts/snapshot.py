#!/usr/bin/env python3
"""Create committed-source UI snapshots and check explained parity differences."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

MANIFEST = "prototype-manifest.json"
GENERATED_DIRS = {".git", "node_modules", ".next", ".venv", "__pycache__", "dist", "build", "target", "coverage"}


def relative(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts or str(p) == "." or value.startswith("-") or "\\" in value:
        raise ValueError("Use a literal repository-relative path: " + value)
    return p.as_posix()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def describe(p, root):
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes prototype: " + str(p))
    if p.is_symlink():
        if not p.resolve().is_relative_to(root.resolve()):
            raise ValueError("Symlink escapes prototype: " + str(p))
        return {"type": "symlink", "target": os.readlink(p)}
    if not p.is_file():
        return {"type": "not-a-file"}
    return {"type": "file", "sha256": digest(p.read_bytes()), "executable": bool(p.stat().st_mode & 0o111)}


def create(args):
    requested = Path(args.repo).resolve()
    repo = Path(git(requested, "rev-parse", "--show-toplevel").decode().strip())
    dest = Path(args.destination).absolute()
    if os.path.lexists(dest):
        raise ValueError("Destination already exists; use a new prototype directory.")
    paths = list(dict.fromkeys(relative(p) for p in args.path))
    if args.fetch:
        if args.remote.startswith("-"):
            raise ValueError("Invalid remote")
        git(repo, "remote", "get-url", args.remote)
        git(repo, "fetch", args.remote)
    if args.ref.startswith("-"):
        raise ValueError("Invalid ref")
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", args.ref + "^{commit}").decode().strip()
    literal_paths = [":(literal)" + p for p in paths]
    tree = git(repo, "ls-tree", "-r", "-z", commit, "--", *literal_paths).split(b"\0")
    if any(row.startswith(b"160000 ") for row in tree):
        raise ValueError("Selected paths contain a submodule; copy and identify its commit separately.")
    blob = git(repo, "archive", "--format=tar", commit, "--", *literal_paths)
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".prd-snapshot-", dir=str(dest.parent))).resolve()
    try:
        with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
            members = archive.getmembers()
            names = {relative(m.name): m for m in members if not m.isdir()}
            if MANIFEST in names:
                raise ValueError("Selected source reserves the prototype manifest name.")
            for selection in paths:
                if not any(p == selection or p.startswith(selection + "/") for p in names):
                    raise ValueError("Selected path is absent or excluded from the Git archive: " + selection)
            links = {name for name, m in names.items() if m.issym()}
            for name, member in names.items():
                for parent in PurePosixPath(name).parents:
                    if parent.as_posix() in links:
                        raise ValueError("Archive path traverses a symlink: " + name)
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if member.issym():
                    if PurePosixPath(member.linkname).is_absolute() or not (target.parent / member.linkname).resolve().is_relative_to(stage):
                        raise ValueError("Archive symlink escapes prototype: " + name)
                    target.symlink_to(member.linkname)
                elif member.isfile():
                    data = archive.extractfile(member).read()
                    target.write_bytes(data)
                    target.chmod(0o755 if member.mode & 0o111 else 0o644)
                else:
                    raise ValueError("Unsupported archive member: " + name)
            files = {name: describe(stage / name, stage) for name in sorted(names)}
        manifest = {"schema_version": 1, "commit": commit, "ref": args.ref, "source_repository": str(repo),
                    "selected_paths": paths, "fetched": args.fetch, "remote": args.remote if args.fetch else None,
                    "offline_reason": args.offline_reason, "created_at": datetime.now(timezone.utc).isoformat(), "files": files}
        (stage / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
        if os.path.lexists(dest):
            raise ValueError("Destination was created concurrently; refusing replacement.")
        stage.rename(dest)
        return {"commit": commit, "files_copied": len(files), "destination": str(dest), "fetched": args.fetch}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def exceptions(allow, key):
    entries = allow.get(key, [])
    if not isinstance(entries, list):
        raise ValueError(key + " must be an array")
    result = {}
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get("path"), str) or not isinstance(e.get("reason"), str) or not e["reason"].strip():
            raise ValueError("Each exception needs a path and nonempty reason")
        p = relative(e["path"])
        if p in result:
            raise ValueError("Duplicate exception: " + p)
        result[p] = e["reason"]
    return result


def verify(args):
    root = Path(args.prototype).resolve()
    manifest = json.loads((root / MANIFEST).read_text())
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), dict) or not manifest["files"]:
        raise ValueError("Invalid or empty source manifest")
    files = manifest["files"]
    for p in files:
        relative(p)
    allow = json.loads(Path(args.allowlist).read_text()) if args.allowlist else {}
    changed_ok, added_ok = exceptions(allow, "changes"), exceptions(allow, "additions")
    if set(changed_ok) - set(files):
        raise ValueError("Change exceptions must name exact baseline files")
    if any(p == f or f.startswith(p + "/") for p in added_ok for f in files):
        raise ValueError("Addition exceptions cannot include baseline paths")
    changed, missing = [], []
    for rel, expected in files.items():
        p = root / rel
        if not os.path.lexists(p):
            missing.append(rel)
        else:
            try:
                different = describe(p, root) != expected
            except (ValueError, RuntimeError):
                different = True
            if different:
                changed.append(rel)
    ignored = {MANIFEST}
    if args.allowlist:
        ap = Path(args.allowlist).resolve()
        if ap.is_relative_to(root):
            ignored.add(ap.relative_to(root).as_posix())
    added = []
    for folder, dirs, names in os.walk(root, followlinks=False):
        linked_dirs = [n for n in dirs if (Path(folder) / n).is_symlink() and n not in GENERATED_DIRS]
        dirs[:] = [n for n in dirs if n not in GENERATED_DIRS and n not in linked_dirs]
        for name in names + linked_dirs:
            rel = (Path(folder) / name).relative_to(root).as_posix()
            if rel not in files and rel not in ignored:
                added.append(rel)
    unexpected_changes = sorted(set(changed + missing) - set(changed_ok))
    unexpected_additions = sorted(p for p in added if not any(p == a or p.startswith(a + "/") for a in added_ok))
    used = sorted(set(changed + missing) & set(changed_ok))
    return {"commit": manifest["commit"], "baseline_files": len(files), "changed": sorted(changed), "missing": sorted(missing),
            "added": sorted(added), "used_change_exceptions": used, "unused_change_exceptions": sorted(set(changed_ok) - set(used)),
            "unexpected_changes": unexpected_changes, "unexpected_additions": unexpected_additions,
            "passed": not unexpected_changes and not unexpected_additions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("create")
    c.add_argument("--repo", required=True)
    c.add_argument("--destination", required=True)
    c.add_argument("--ref", required=True)
    c.add_argument("--remote", default="origin")
    c.add_argument("--path", action="append", required=True)
    freshness = c.add_mutually_exclusive_group(required=True)
    freshness.add_argument("--fetch", action="store_true")
    freshness.add_argument("--offline-reason")
    v = sub.add_parser("verify")
    v.add_argument("--prototype", required=True)
    v.add_argument("--allowlist")
    args = parser.parse_args()
    try:
        if args.command == "create" and args.offline_reason is not None and not args.offline_reason.strip():
            raise ValueError("Offline reason must be nonempty")
        report = create(args) if args.command == "create" else verify(args)
        print(json.dumps(report, indent=2))
        return 0 if report.get("passed", True) else 1
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, tarfile.TarError, subprocess.CalledProcessError) as e:
        # Avoid printing git stderr: remote configuration may contain credentials.
        message = "Git operation failed; verify repository, remote, ref and selected paths." if isinstance(e, subprocess.CalledProcessError) else str(e)
        print("error: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
