"""Cron job management module.

Provides functions to list, create, and delete crontab entries
for the current user. All write operations require user confirmation.
"""

import subprocess


def cron_list() -> str:
    """List all current crontab entries."""
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        if "no crontab" in result.stderr.lower():
            return "No crontab entries found."
        return f"Error reading crontab: {result.stderr}"
    lines = result.stdout.strip().split("\n")
    if not lines or lines == [""]:
        return "No crontab entries found."
    output = ["Current crontab entries:\n"]
    for i, line in enumerate(lines):
        prefix = f"  [{i}] " if not line.startswith("#") else f"  [#] "
        output.append(f"{prefix}{line}")
    return "\n".join(output)


def cron_create(schedule: str, command: str) -> str:
    """Add a new cron job after user confirmation.

    Args:
        schedule: Cron schedule expression (e.g. '0 9 * * *' for daily at 9am)
        command: Shell command to execute
    """
    entry = f"{schedule} {command}"
    print(f"\n{'='*60}")
    print(f"CRON JOB CONFIRMATION")
    print(f"{'='*60}")
    print(f"  Schedule: {schedule}")
    print(f"  Command:  {command}")
    print(f"  Full entry: {entry}")
    print(f"{'='*60}")

    try:
        confirm = input("Add this cron job? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "Cancelled by user."

    if confirm != "y":
        return "Cron job creation cancelled by user."

    # Get existing crontab
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    # Append new entry
    new_crontab = existing.rstrip("\n") + "\n" + entry + "\n"
    result = subprocess.run(
        ["crontab", "-"], input=new_crontab, capture_output=True, text=True
    )

    if result.returncode != 0:
        return f"Error creating cron job: {result.stderr}"
    return f"Cron job created: {entry}"


def cron_delete(index: int) -> str:
    """Delete a cron job by its index number after user confirmation.

    Args:
        index: The index of the cron job to delete (from cron_list output)
    """
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return "No crontab entries to delete."

    lines = result.stdout.strip().split("\n")
    # Build index mapping (only non-comment lines get numeric indices)
    indexed = []
    for line in lines:
        if not line.startswith("#"):
            indexed.append(line)

    if index < 0 or index >= len(indexed):
        return f"Invalid index {index}. Valid range: 0-{len(indexed)-1}"

    target = indexed[index]
    print(f"\n{'='*60}")
    print(f"CRON JOB DELETE CONFIRMATION")
    print(f"{'='*60}")
    print(f"  Deleting [{index}]: {target}")
    print(f"{'='*60}")

    try:
        confirm = input("Delete this cron job? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "Cancelled by user."

    if confirm != "y":
        return "Cron job deletion cancelled by user."

    # Remove the target line
    remaining = [line for line in lines if line != target]
    new_crontab = "\n".join(remaining) + "\n" if remaining else ""

    if new_crontab.strip():
        result = subprocess.run(
            ["crontab", "-"], input=new_crontab, capture_output=True, text=True
        )
    else:
        result = subprocess.run(["crontab", "-r"], capture_output=True, text=True)

    if result.returncode != 0:
        return f"Error deleting cron job: {result.stderr}"
    return f"Cron job deleted: {target}"


if __name__ == "__main__":
    print(cron_list())
