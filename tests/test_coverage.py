import importlib.util
import json
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


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.contract = json.loads((ROOT / "assets/coverage-contract.example.json").read_text())
        self.results = json.loads((ROOT / "assets/scenario-results.example.json").read_text())
        for r in self.results["results"]:
            # Synthetic helper-test artifacts only; these are not UI-run evidence.
            for name in [r["recording"], *r["screenshots"]]:
                p = self.root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"synthetic helper-test fixture")

    def tearDown(self):
        self.temp.cleanup()

    def check(self):
        return MODULE.check(self.contract, self.results, self.root)

    def test_complete_artifacts_pass_but_review_stays_pending(self):
        report = self.check()
        self.assertTrue(report["coverage_passed"])
        self.assertEqual(report["review_status"], "pending")
        self.assertEqual(report["visited_screens"], ["S1", "S2"])

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

    def test_deep_link_bypass_is_rejected_and_native_log_is_allowed(self):
        self.results["results"][0]["entry_screen"] = "S2"
        self.assertFalse(self.check()["coverage_passed"])
        self.results["results"][0]["entry_screen"] = "S1"
        self.results["results"][0]["recording"] = "native-run.log"
        (self.root / "native-run.log").write_text("synthetic native runner log")
        self.assertTrue(self.check()["coverage_passed"])

    def test_artifact_paths_cannot_escape_root(self):
        outside = self.root.parent / (self.root.name + "-outside")
        outside.write_bytes(b"fixture")
        try:
            (self.root / "linked-recording").symlink_to(outside)
            for path in [str(outside), "../" + outside.name, "linked-recording"]:
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
        contract.write_text("invalid JSON")
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
