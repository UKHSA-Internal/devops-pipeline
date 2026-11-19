"""The final step: needs the files every suite collected, without running the suites again."""

import pathlib
import sys

files = sorted(pathlib.Path(".").glob(".coverage.*"))
names = [path.suffix[1:] for path in files]
if names != ["lint", "static", "unit"]:
    sys.exit(f"expected coverage files from every suite, found: {names}")
print(f"combined {sum(int(path.read_text()) for path in files)} tests from {', '.join(names)}")
