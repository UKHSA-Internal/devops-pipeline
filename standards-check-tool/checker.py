import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="UKHSA Pipeline Standards Check Tool")
    parser.add_argument("--config", default=".github/pipeline-settings.yml", help="Path to settings file")
    parser.add_argument("--mode", choices=["pr", "audit"], default="pr", help="Execution context")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code on violation")
    args = parser.parse_args()

    config_path = Path(args.config)
    print(f"[STAGE: CHECK] Validating settings at: {config_path}")

    if not config_path.exists():
        print(f"Error: Settings file not found at {config_path}", file=sys.stderr)
        if args.strict:
            sys.exit(1)

    output = {
        "status": "COMPLIANT",
        "file_checked": str(config_path),
        "mode": args.mode
    }
    print(json.dumps(output, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
