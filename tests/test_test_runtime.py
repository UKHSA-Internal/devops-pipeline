"""Tests for the Test step's runtime resolution.

The logic lives in the "Resolve Test Runtime" step of
packages/shared-workflows/actions/test/action.yml. These tests extract that
script from the action and run it with bash, so the shell behaviour is tested
rather than a copy of it.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ACTION_PATH = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "shared-workflows"
    / "actions"
    / "test"
    / "action.yml"
)
STEP_NAME = "Resolve Test Runtime"


def runtime_script():
    action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
    for step in action["runs"]["steps"]:
        if step.get("name") == STEP_NAME:
            return step["run"]
    raise AssertionError(f"No '{STEP_NAME}' step in {ACTION_PATH}")


class ResolveTestRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("bash") is None:
            raise unittest.SkipTest("bash is required to run the action's script")
        cls.script = runtime_script()

    def run_step(self, language, version_files=()):
        """Run the step against a throwaway service directory; return the result and outputs."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = root / "service"
            service.mkdir()
            for name, content in version_files:
                (service / name).write_text(content, encoding="utf-8")

            output_path = root / "github_output"
            summary_path = root / "github_summary"
            output_path.touch()
            summary_path.touch()

            completed = subprocess.run(
                ["bash", "-c", self.script],
                capture_output=True,
                text=True,
                cwd=root,
                env={
                    **os.environ,
                    "SERVICE_DIRECTORY": "service",
                    "LANGUAGE": language,
                    "GITHUB_OUTPUT": str(output_path),
                    "GITHUB_STEP_SUMMARY": str(summary_path),
                },
            )
            outputs = dict(
                line.split("=", 1)
                for line in output_path.read_text(encoding="utf-8").splitlines()
                if "=" in line
            )
            return completed, outputs, summary_path.read_text(encoding="utf-8")

    def test_python_resolves_the_python_version_file(self):
        completed, outputs, summary = self.run_step("python", [(".python-version", "3.11\n")])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(outputs["language"], "python")
        self.assertEqual(outputs["version_file"], "service/.python-version")
        self.assertIn(".python-version", summary)

    def test_node_resolves_nvmrc(self):
        completed, outputs, _ = self.run_step("node", [(".nvmrc", "22\n")])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(outputs["language"], "node")
        self.assertEqual(outputs["version_file"], "service/.nvmrc")

    def test_node_falls_back_to_node_version_file(self):
        completed, outputs, _ = self.run_step("node", [(".node-version", "22\n")])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(outputs["version_file"], "service/.node-version")

    def test_node_prefers_nvmrc_over_node_version(self):
        completed, outputs, _ = self.run_step(
            "node", [(".nvmrc", "22\n"), (".node-version", "20\n")]
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(outputs["version_file"], "service/.nvmrc")

    def test_language_is_matched_case_insensitively(self):
        completed, outputs, _ = self.run_step("  Python  ", [(".python-version", "3.11\n")])

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(outputs["language"], "python")

    def test_missing_python_version_file_fails_and_names_the_file(self):
        completed, outputs, _ = self.run_step("python")

        self.assertEqual(completed.returncode, 1)
        self.assertIn(".python-version", completed.stderr)
        self.assertNotIn("language", outputs)

    def test_missing_node_version_file_names_both_accepted_files(self):
        completed, _, _ = self.run_step("node")

        self.assertEqual(completed.returncode, 1)
        self.assertIn(".nvmrc or .node-version", completed.stderr)

    def test_unsupported_language_warns_and_sets_up_no_runtime(self):
        completed, outputs, summary = self.run_step("go")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(outputs["language"], "")
        self.assertIn("WARNING", completed.stdout)
        self.assertIn("Runtime: **none**", summary)

    def test_missing_language_warns_and_sets_up_no_runtime(self):
        completed, outputs, summary = self.run_step("")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(outputs["language"], "")
        self.assertIn("Runtime: **none**", summary)


if __name__ == "__main__":
    unittest.main()
