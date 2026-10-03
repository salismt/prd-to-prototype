import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/snapshot.py"


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "source"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "frontend/src").mkdir(parents=True)
        (self.repo / "frontend/src/home.tsx").write_text("original home\n")
        (self.repo / "frontend/src/[id].tsx").write_text("dynamic route\n")
        (self.repo / "frontend/logo.svg").write_text("synthetic logo\n")
        (self.repo / "package.json").write_text("{}\n")
        (self.repo / "frontend/logo-link.svg").symlink_to("logo.svg")
        self.git("add", ".")
        self.git("commit", "-m", "Fixture")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.dest = self.root / "prototype"

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.PIPE, text=True)

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)

    def create(self, *extra):
        return self.run_script("create", "--repo", self.repo, "--destination", self.dest, "--ref", "HEAD", "--offline-reason", "Local synthetic fixture", "--path", "frontend", *extra)

    def test_copy_is_committed_preserves_modes_symlinks_and_does_not_overwrite(self):
        file = self.repo / "frontend/src/home.tsx"
        file.write_text("uncommitted change")
        result = self.create("--path", "package.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.dest / "frontend/src/home.tsx").read_text(), "original home\n")
        self.assertTrue((self.dest / "frontend/logo-link.svg").is_symlink())
        self.assertTrue((self.dest / "frontend/src/[id].tsx").exists())
        manifest = json.loads((self.dest / "prototype-manifest.json").read_text())
        self.assertEqual(manifest["commit"], self.sha)
        self.assertFalse(manifest["fetched"])
        self.assertEqual(self.create().returncode, 2)
        self.assertEqual(file.read_text(), "uncommitted change")

    def test_literal_selected_route_path(self):
        r = self.run_script("create", "--repo", self.repo, "--destination", self.dest, "--ref", "HEAD", "--offline-reason", "Fixture", "--path", "frontend/src/[id].tsx")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.dest / "frontend/src/[id].tsx").exists())
        self.assertFalse((self.dest / "frontend/src/home.tsx").exists())

    def test_fetch_records_remote_commit(self):
        bare = self.root / "remote.git"
        subprocess.check_call(["git", "init", "--bare", str(bare)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "origin", "main")
        r = self.run_script("create", "--repo", self.repo, "--destination", self.dest, "--ref", "origin/main", "--fetch", "--path", "frontend")
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads((self.dest / "prototype-manifest.json").read_text())
        self.assertTrue(m["fetched"])
        self.assertEqual(m["commit"], self.sha)

    def test_changed_shell_missing_file_and_unexplained_addition_fail(self):
        self.assertEqual(self.create().returncode, 0)
        self.assertEqual(self.run_script("verify", "--prototype", self.dest).returncode, 0)
        (self.dest / "frontend/src/home.tsx").write_text("replacement home")
        (self.dest / "frontend/logo.svg").unlink()
        (self.dest / "extra.css").write_text("green backdrop")
        r = self.run_script("verify", "--prototype", self.dest)
        self.assertEqual(r.returncode, 1, r.stderr)
        report = json.loads(r.stdout)
        self.assertIn("frontend/src/home.tsx", report["unexpected_changes"])
        self.assertIn("frontend/logo.svg", report["unexpected_changes"])
        self.assertEqual(report["unexpected_additions"], ["extra.css"])

    def test_specific_explained_changes_and_new_feature_folder_pass(self):
        self.assertEqual(self.create().returncode, 0)
        (self.dest / "frontend/src/home.tsx").write_text("Authorized home feature")
        (self.dest / "frontend/new-feature").mkdir()
        (self.dest / "frontend/new-feature/view.tsx").write_text("new UI")
        allow = self.dest / "parity.json"
        allow.write_text(json.dumps({"changes": [{"path": "frontend/src/home.tsx", "reason": "PRD explicitly changes home"}], "additions": [{"path": "frontend/new-feature", "reason": "New scoped feature"}]}))
        r = self.run_script("verify", "--prototype", self.dest, "--allowlist", allow)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["used_change_exceptions"], ["frontend/src/home.tsx"])
        allow.write_text(json.dumps({"additions": [{"path": "frontend", "reason": "Broad exception"}]}))
        self.assertEqual(self.run_script("verify", "--prototype", self.dest, "--allowlist", allow).returncode, 2)

    def test_parent_symlink_cannot_fake_baseline_parity(self):
        self.assertEqual(self.create().returncode, 0)
        import shutil
        shutil.rmtree(self.dest / "frontend/src")
        (self.dest / "frontend/src").symlink_to(self.repo / "frontend/src")
        r = self.run_script("verify", "--prototype", self.dest)
        self.assertEqual(r.returncode, 1)
        self.assertIn("frontend/src/home.tsx", json.loads(r.stdout)["unexpected_changes"])

    def test_escaping_symlink_and_absent_selection_leave_no_destination(self):
        (self.repo / "frontend/escape").symlink_to("../../outside")
        self.git("add", ".")
        self.git("commit", "-m", "Unsafe link fixture")
        r = self.create()
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertFalse(self.dest.exists())
        r = self.run_script("create", "--repo", self.repo, "--destination", self.dest, "--ref", "HEAD", "--offline-reason", "Fixture", "--path", "missing")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(self.dest.exists())

    def test_submodule_and_traversal_are_refused(self):
        self.git("update-index", "--add", "--cacheinfo", "160000," + self.sha + ",frontend/vendor")
        self.git("commit", "-m", "Submodule fixture")
        self.assertEqual(self.create().returncode, 2)
        self.assertFalse(self.dest.exists())
        r = self.run_script("create", "--repo", self.repo, "--destination", self.dest, "--ref", "HEAD", "--offline-reason", "Fixture", "--path", "../outside")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
