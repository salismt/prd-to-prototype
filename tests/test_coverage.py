from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("coverage_checker", ROOT / "scripts/check_coverage.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
# Synthetic helper-test fixtures only: real signatures plus padding, not UI-run evidence.
PNG, ZIP, WEBM, JPG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16, b"PK\x03\x04" + b"\0" * 16, b"\x1a\x45\xdf\xa3" + b"\0" * 16, b"\xff\xd8\xff" + b"\0" * 16


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.contract = json.loads((ROOT / "assets/coverage-contract.example.json").read_text())
        self.results = json.loads((ROOT / "assets/scenario-results.example.json").read_text())
        self.started = datetime.now(timezone.utc) - timedelta(seconds=30)
        self.results["run_started_at"] = self.started.isoformat()
        for r in self.results["results"]:
            self.write(r["recording"], ZIP)
            for name in r["screenshots"]:
                self.write(name, PNG)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def check(self):
        return MODULE.check(self.contract, self.results, self.root)

    def test_complete_artifacts_pass_but_review_stays_pending(self):
        report = self.check()
        self.assertTrue(report["coverage_passed"])
        self.assertEqual(report["review_status"], "pending")
        self.assertEqual(report["visited_screens"], ["S1", "S2"])
        self.assertEqual(report["runner"], {"name": "playwright", "version": "example-only"})

    def test_declared_screens_are_not_actual_visits(self):
        self.results["results"][0]["visited_screens"] = ["S1"]
        report = self.check()
        self.assertFalse(report["coverage_passed"])
        self.assertTrue(any("required screens not visited" in f for f in report["failures"]))

    def test_missing_duplicate_and_unknown_results_fail(self):
        self.results["results"].pop()
        self.results["results"].append(deepcopy(self.results["results"][0]))
        rogue = deepcopy(self.results["results"][0])
        rogue["id"] = "AC-99"
        self.results["results"].append(rogue)
        report = self.check()
        self.assertFalse(report["coverage_passed"])
        self.assertEqual(report["missing_ids"], ["AC-02"])
        self.assertEqual(report["duplicate_ids"], ["AC-01"])
        self.assertEqual(report["unknown_ids"], ["AC-99"])

    def test_skipped_failed_and_missing_artifacts_never_count_as_passed(self):
        for status in ["skipped", "failed", "pending"]:
            with self.subTest(status=status):
                self.results["results"][0]["status"] = status
                self.assertFalse(self.check()["coverage_passed"])
        self.results["results"][0]["status"] = "passed"
        (self.root / self.results["results"][0]["recording"]).unlink()
        self.assertFalse(self.check()["coverage_passed"])
        (self.root / self.results["results"][1]["screenshots"][0]).write_bytes(b"")
        self.assertTrue(any("missing, empty" in f for f in self.check()["failures"]))

    def test_deep_link_bypass_and_native_log_recording_are_rejected(self):
        self.results["results"][0]["entry_screen"] = "S2"
        self.assertFalse(self.check()["coverage_passed"])
        self.results["results"][0]["entry_screen"] = "S1"
        self.results["results"][0]["recording"] = "native-run.log"
        self.write("native-run.log", b"synthetic native runner log")
        self.assertTrue(any("recording must be one of .webm, .zip" in f for f in self.check()["failures"]))
        self.results["results"][0]["recording"] = "AC-01.webm"
        self.write("AC-01.webm", WEBM)
        self.results["results"][0]["screenshots"] = ["AC-01.jpg"]
        self.write("AC-01.jpg", JPG)
        self.assertTrue(self.check()["coverage_passed"])

    def test_fake_text_artifacts_and_signature_mismatch_are_rejected(self):
        self.write(self.results["results"][0]["recording"], b"x\n")
        self.write(self.results["results"][0]["screenshots"][0], b"x\n")
        report = self.check()
        self.assertFalse(report["coverage_passed"])
        self.assertEqual(sum("AC-01: artifact content does not match its extension" in f for f in report["failures"]), 2)
        self.assertEqual(report["passed_ids"], ["AC-02"])
        self.write(self.results["results"][1]["screenshots"][0], ZIP)
        self.assertTrue(any("AC-02: artifact content does not match" in f for f in self.check()["failures"]))

    def test_artifact_older_than_run_is_rejected(self):
        old = (self.started - timedelta(minutes=5)).timestamp()
        p = self.root / self.results["results"][0]["screenshots"][0]
        os.utime(p, (old, old))
        report = self.check()
        self.assertFalse(report["coverage_passed"])
        self.assertTrue(any("AC-01: artifact predates this run" in f for f in report["failures"]))
        self.assertEqual(report["passed_ids"], ["AC-02"])

    def test_artifact_shared_across_acs_fails_both(self):
        self.results["results"][1]["recording"] = "./" + self.results["results"][0]["recording"]
        report = self.check()
        self.assertFalse(report["coverage_passed"])
        self.assertEqual(report["passed_ids"], [])
        self.assertTrue(any(f.startswith("AC-01: artifact shared with AC-02") for f in report["failures"]))
        self.assertTrue(any(f.startswith("AC-02: artifact shared with AC-01") for f in report["failures"]))

    def test_malformed_row_is_a_per_ac_failure_not_an_error(self):
        self.results["results"][0]["visited_screens"] = []
        self.results["results"].append("not a row")
        report = self.check()
        self.assertFalse(report["coverage_passed"])
        self.assertTrue(any(f.startswith("AC-01: visited_screens must be") for f in report["failures"]))
        self.assertTrue(any(f.startswith("results[2]: id must be") for f in report["failures"]))
        self.assertEqual(report["passed_ids"], ["AC-02"])

    def test_non_ac_pattern_ids_are_accepted(self):
        for ident in ["PRD1-login-happy-path", "US-7.3", "req_42"]:
            with self.subTest(ident=ident):
                self.contract["acceptance"][0]["id"] = self.results["results"][0]["id"] = ident
                self.assertTrue(self.check()["coverage_passed"])
        self.contract["acceptance"][0]["id"] = ""
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_run_metadata_is_an_error(self):
        for key, value in [("run_started_at", None), ("run_started_at", "2026-01-01T00:00:00"), ("run_started_at", "yesterday"), ("runner", None), ("runner", {"name": "playwright"})]:
            with self.subTest(key=key, value=value):
                results = deepcopy(self.results)
                if value is None:
                    del results[key]
                else:
                    results[key] = value
                with self.assertRaises(ValueError):
                    MODULE.check(self.contract, results, self.root)

    def test_artifact_paths_cannot_escape_root(self):
        outside = self.root.parent / (self.root.name + "-outside")
        outside.write_bytes(ZIP)
        try:
            (self.root / "linked-recording.zip").symlink_to(outside)
            for path in [str(outside), "../" + outside.name, "linked-recording.zip"]:
                with self.subTest(path=path):
                    self.results["results"][0]["recording"] = path
                    self.assertFalse(self.check()["coverage_passed"])
        finally:
            outside.unlink()

    def test_malformed_mapping_and_stale_review_are_errors(self):
        self.contract["acceptance"][0]["screens"] = ["S99"]
        with self.assertRaises(ValueError):
            self.check()
        self.contract["acceptance"][0]["screens"] = ["S1", "S2"]
        self.results["review"] = {"status": "approved", "actor": "Product owner", "prototype_version": "older", "evidence": "review record"}
        with self.assertRaises(ValueError):
            self.check()
        self.results["review"]["prototype_version"] = self.results["prototype_version"]
        self.assertEqual(self.check()["review_status"], "approved")

    def test_cli_exit_codes_and_report_are_observable(self):
        contract, results, out = self.root / "contract.json", self.root / "results.json", self.root / "report.json"
        contract.write_text(json.dumps(self.contract))
        results.write_text(json.dumps(self.results))
        command = [sys.executable, str(ROOT / "scripts/check_coverage.py"), "--contract", str(contract), "--results", str(results), "--artifact-root", str(self.root), "--output", str(out)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertTrue(json.loads(out.read_text())["coverage_passed"])
        self.results["results"][0]["status"] = "skipped"
        results.write_text(json.dumps(self.results))
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        self.results["results"][0]["status"] = "passed"
        self.results["results"][0]["visited_screens"] = []
        results.write_text(json.dumps(self.results))
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        del self.results["runner"]
        results.write_text(json.dumps(self.results))
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
        contract.write_text("invalid JSON")
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
