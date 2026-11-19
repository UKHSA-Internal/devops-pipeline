import unittest
from pathlib import Path

APP_DIRECTORY = Path(__file__).resolve().parents[2]


class ImageContentsTests(unittest.TestCase):
    def test_every_copied_source_exists(self):
        sources = [
            line.split()[1]
            for line in (APP_DIRECTORY / "Dockerfile").read_text(encoding="utf-8").splitlines()
            if line.startswith("COPY ")
        ]

        self.assertTrue(sources, "the Dockerfile copies nothing into the image")
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue((APP_DIRECTORY / source).exists())


if __name__ == "__main__":
    unittest.main()
