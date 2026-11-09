"""Pipeline settings checker.

Checks a repository's .github/pipeline-settings.yml and reports whether it is
ready to onboard to the shared pipeline. The Check step of every pipeline run
uses the same tool. The rules themselves are in rules.py.
"""

import argparse
import json
from pathlib import Path

import yaml

from rules import ERROR, WARNING, check

DEFAULT_SETTINGS = Path(".github") / "pipeline-settings.yml"
SYMBOLS = {ERROR: "✗", WARNING: "!"}


def file_problem(path: Path, message: str) -> dict:
    return {"field": str(path), "severity": ERROR, "message": message, "rule": None}


def load_settings(path: Path):
    """Return (settings, None), or (None, problem) if the file can't be used."""
    if not path.is_file():
        return None, file_problem(path, "file not found")
    try:
        settings = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        return None, file_problem(path, f"is not valid YAML{where}")
    except (OSError, UnicodeDecodeError) as error:
        return None, file_problem(path, f"cannot be read: {error}")
    if not isinstance(settings, dict):
        return None, file_problem(path, "must contain the settings as a YAML mapping")
    return settings, None


def exit_code(problems: list, strict: bool, report_only: bool) -> int:
    if report_only:
        return 0
    failing = problems if strict else [item for item in problems if item["severity"] == ERROR]
    return 1 if failing else 0


def create_report(path: Path, problems: list, status: int) -> dict:
    errors = sum(item["severity"] == ERROR for item in problems)
    return {
        "settings_file": str(path),
        "ready": errors == 0,
        "exit_code": status,
        "summary": {"errors": errors, "warnings": len(problems) - errors},
        "problems": problems,
    }


def headline(report: dict) -> str:
    counts = [
        f"{count} {name}{'' if count == 1 else 's'}"
        for name, count in (("error", report["summary"]["errors"]), ("warning", report["summary"]["warnings"]))
        if count
    ]
    return f"{'Ready' if report['ready'] else 'Not ready'}: {', '.join(counts) or 'no problems'}"


def describe(item: dict) -> str:
    rule = f" ({item['rule']})" if item["rule"] else ""
    return f"{item['field']} – {item['message']}{rule}"


def as_text(report: dict) -> str:
    lines = [f"Settings file: {report['settings_file']}", headline(report)]
    if report["problems"]:
        lines.append("")
        lines.extend(f"{SYMBOLS[item['severity']]} {describe(item)}" for item in report["problems"])
    return "\n".join(lines)


def as_markdown(report: dict) -> str:
    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("`", "'")

    lines = [
        "### Settings check",
        "",
        f"**{headline(report)}**",
        "",
        f"Settings file: `{cell(report['settings_file'])}`",
    ]
    if report["problems"]:
        lines += ["", "| | Field | Problem | Rule |", "| --- | --- | --- | --- |"]
        lines.extend(
            f"| {SYMBOLS[item['severity']]} {item['severity']} | `{cell(item['field'])}` "
            f"| {cell(item['message'])} | {item['rule'] or ''} |"
            for item in report["problems"]
        )
    return "\n".join(lines) + "\n"


def as_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


FORMATS = {"text": as_text, "json": as_json, "markdown": as_markdown}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a repository's pipeline settings and report whether it is ready to onboard to the shared pipeline."
    )
    parser.add_argument(
        "repository", nargs="?", default=".", help="repository folder to check (default: the current folder)"
    )
    parser.add_argument("--settings", help=f"settings file to check, instead of REPOSITORY/{DEFAULT_SETTINGS}")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true", help="fail on warnings as well as errors")
    mode.add_argument("--report-only", action="store_true", help="report problems, but always exit 0")
    parser.add_argument("--format", choices=FORMATS, default="text", help="output format (default: text)")
    args = parser.parse_args(argv)

    path = Path(args.settings) if args.settings else Path(args.repository) / DEFAULT_SETTINGS
    settings, problem = load_settings(path)
    problems = [problem] if problem else sorted(check(settings), key=lambda item: item["severity"] != ERROR)
    report = create_report(path, problems, exit_code(problems, args.strict, args.report_only))
    print(FORMATS[args.format](report))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
