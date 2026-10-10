"""Safely clear AARON-1 tasks created by you, from this machine's database.

This script NEVER runs automatically. It only performs deletion when invoked
with --yes, saves an SQLite backup first, and leaves imported tasks, calendar
events, memories, chat history, and training examples untouched.

Usage:
    .venv312/bin/python clear_my_tasks.py        # Preview
    .venv312/bin/python clear_my_tasks.py --yes  # Back up and clear
"""
from __future__ import annotations

import argparse
import sys

from planner import manually_added_task_count, clear_manually_added_tasks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true",
        help="Confirm deletion of all manually added tasks after a DB backup",
    )
    args = parser.parse_args(argv)
    count = manually_added_task_count()
    print(f"AARON-1: {count} manually added task(s) (completed included).")
    print("Imported school/email assignments, calendar events, memories, "
          "and AI training data will NOT be deleted.")
    if not args.yes:
        print("Preview only. Run again with --yes to back up and remove them.")
        return 0
    try:
        deleted, backup = clear_manually_added_tasks(expected_count=count)
    except (OSError, ValueError) as exc:
        print(f"Could not delete tasks: {exc}", file=sys.stderr)
        return 1
    print(f"Deleted {deleted} manually added task(s).")
    if backup:
        print(f"Full SQLite backup saved at: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
