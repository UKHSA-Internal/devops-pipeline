import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReadmeSimulatedStagesTests(unittest.TestCase):
    def test_readme_lists_exactly_the_actions_that_output_simulated(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Simulated stages", 1)[1].split("\n## ", 1)[0]
        listed = set(re.findall(r"`(packages/shared-workflows/actions/[^`]+)`", section))

        simulated = {
            str(path.parent.relative_to(ROOT))
            for path in (ROOT / "packages" / "shared-workflows" / "actions").glob("*/action.yml")
            if "simulated=true" in path.read_text(encoding="utf-8")
        }

        self.assertEqual(listed, simulated)


if __name__ == "__main__":
    unittest.main()
