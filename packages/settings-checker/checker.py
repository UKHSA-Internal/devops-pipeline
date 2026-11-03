import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="UKHSA Pipeline Standards Check Tool")
    parser.add_argument("--config", default=".github/pipeline-settings.yml", help="Path to settings file")
    parser.add_argument("--mode", choices=["pr", "audit"], default="pr", help="Execution context")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Retained for compatibility; an unreadable settings file always fails",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    print(f"[STEP: CHECK] Checking settings file: {config_path}")

    try:
        with config_path.open("rb"):
            pass
    except OSError as error:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "file_checked": str(config_path),
                    "mode": args.mode,
                    "error": f"Unable to read settings file: {error}",
                },
                indent=2,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "VALIDATION_PENDING",
                "file_checked": str(config_path),
                "mode": args.mode,
                "message": "Schema validation is not implemented; this check only confirms the file can be read.",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
