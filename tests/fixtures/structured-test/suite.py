"""A tiny suite: writes a JUnit file and a coverage data file, as a real suite would."""

import pathlib
import sys

name, tests = sys.argv[1], int(sys.argv[2])
pathlib.Path("test-results").mkdir(exist_ok=True)
pathlib.Path(f"test-results/{name}.xml").write_text(
    f'<testsuite name="{name}" tests="{tests}" failures="0" errors="0" time="0.1"/>\n', encoding="utf-8"
)
pathlib.Path(f".coverage.{name}").write_text(f"{tests}\n", encoding="utf-8")
print(f"suite {name}: {tests} tests passed")
