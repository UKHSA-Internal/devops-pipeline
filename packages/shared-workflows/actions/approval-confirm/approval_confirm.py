#!/usr/bin/env python3
"""Log an approval marker, and reject an approval given after the approval window closed."""

import os
import sys
from datetime import datetime, timedelta, timezone

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def is_expired(opened_at: str, now: datetime, max_age_hours: float) -> bool:
    opened = datetime.strptime(opened_at, TIME_FORMAT).replace(tzinfo=timezone.utc)
    return now - opened > timedelta(hours=max_age_hours)


def main() -> int:
    environment = os.environ["APPROVAL_ENVIRONMENT"]
    groups = os.environ["APPROVAL_GROUPS"]
    opened_at = os.environ["GATE_OPENED_AT"]
    max_age_hours = float(os.environ["MAX_AGE_HOURS"])

    try:
        expired = is_expired(opened_at, datetime.now(timezone.utc), max_age_hours)
    except ValueError:
        print(f"::error title=Approval::Invalid gate open time {opened_at!r}; failing closed.")
        return 1
    if expired:
        print(
            f"::error title=Approval expired::{environment} was approved more than {max_age_hours:g} hours "
            f"after the gate opened ({opened_at}). Re-run the pipeline to request a fresh approval."
        )
        print(f"[STEP: APPROVAL] {environment} EXPIRED for group(s): {groups}")
        return 1
    print(f"[STEP: APPROVAL] {environment} approved for group(s): {groups}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
