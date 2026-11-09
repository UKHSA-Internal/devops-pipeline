"""Placeholder test run by service.test_command; replace it with the service's real tests."""

import unittest
from pathlib import Path

SERVICE_DIRECTORY = Path(__file__).resolve().parents[1]


class PlaceholderTests(unittest.TestCase):
    def test_pipeline_settings_exist(self):
        self.assertTrue((SERVICE_DIRECTORY / ".github" / "pipeline-settings.yml").is_file())


if __name__ == "__main__":
    unittest.main()
