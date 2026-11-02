import unittest
from pathlib import Path

APP_DIRECTORY = Path(__file__).resolve().parents[1]


class SampleAppTests(unittest.TestCase):
    def test_dockerfile_exists_for_build_stage(self):
        self.assertTrue((APP_DIRECTORY / "Dockerfile").is_file())

    def test_readme_is_packaged_into_image(self):
        self.assertTrue((APP_DIRECTORY / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
