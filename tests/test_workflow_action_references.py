import ast
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
LOCAL_ACTION = "./packages/shared-workflows/actions/"


def release_pin_pattern():
    """Return the regex the release's pinning step uses to rewrite action references."""
    release = (WORKFLOWS / "release-cicd-platform.yml").read_text(encoding="utf-8")
    literal = re.search(r'(r"\^\(\[ \\t\]\*uses:[^\n]*?)",\n', release)
    if literal is None:
        raise AssertionError("Could not find the pinning pattern in release-cicd-platform.yml")
    return re.compile(ast.literal_eval(literal.group(1) + '"'), re.MULTILINE)


class LocalActionReferenceTests(unittest.TestCase):
    def setUp(self):
        self.text = (WORKFLOWS / "standard-pipeline.yml").read_text(encoding="utf-8")
        self.jobs = yaml.safe_load(self.text)["jobs"]

    def local_jobs(self):
        return {
            name: job
            for name, job in self.jobs.items()
            if any(str(step.get("uses", "")).startswith(LOCAL_ACTION) for step in job.get("steps", []))
        }

    def test_jobs_with_local_actions_check_out_before_using_them(self):
        jobs = self.local_jobs()
        self.assertIn("approval-guard", jobs)
        self.assertIn("approve", jobs)
        for name, job in jobs.items():
            with self.subTest(job=name):
                uses = [str(step.get("uses", "")) for step in job["steps"]]
                first_local = next(i for i, ref in enumerate(uses) if ref.startswith(LOCAL_ACTION))
                self.assertTrue(
                    any(ref.startswith("actions/checkout@") for ref in uses[:first_local]),
                    "no actions/checkout step before the first local action",
                )

    def test_every_local_action_reference_is_pinned_by_the_release(self):
        references = re.findall(r"^[ \t]*uses:[ \t]*(\./packages/\S*)[ \t]*$", self.text, re.MULTILINE)
        pinned = release_pin_pattern().findall(self.text)

        self.assertGreater(len(references), 0)
        self.assertEqual(len(pinned), len(references), "a ./packages reference is not covered by the pinning step")
        self.assertEqual(self.text.count("uses: ./packages/"), len(references))


if __name__ == "__main__":
    unittest.main()
