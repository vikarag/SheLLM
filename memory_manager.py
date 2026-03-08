"""Shared memory manager for LLM chat scripts.

Stores memories in SQLite with FTS5 full-text search and auto-archival.
"""

import json
import os
from datetime import datetime, timedelta

from db import get_connection

_MEMORY_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")

MAX_ACTIVE = 200
ARCHIVE_DAYS = 90


def _migrate_from_json():
    """One-time migration from memory.json to SQLite."""
    if not os.path.exists(_MEMORY_JSON):
        return
    conn = get_connection()
    # Only migrate if DB is empty
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    if count > 0:
        return
    try:
        with open(_MEMORY_JSON) as f:
            entries = json.load(f)
        for entry in entries:
            conn.execute(
                "INSERT INTO memories (timestamp, source, content, tags) VALUES (?, ?, ?, ?)",
                (
                    entry.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    entry.get("source", "unknown"),
                    entry.get("content", ""),
                    json.dumps(entry.get("tags", []), ensure_ascii=False),
                ),
            )
        conn.commit()
        # Rename original file as backup
        os.rename(_MEMORY_JSON, _MEMORY_JSON + ".bak")
    except Exception:
        conn.rollback()


def _auto_archive():
    """Archive old memories to keep the active set manageable."""
    conn = get_connection()
    now = datetime.now()
    cutoff = (now - timedelta(days=ARCHIVE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    archived_at = now.strftime("%Y-%m-%d %H:%M:%S")

    # Archive memories older than ARCHIVE_DAYS (except system source)
    conn.execute(
        "UPDATE memories SET archived = 1, archived_at = ? "
        "WHERE archived = 0 AND source != 'system' AND timestamp < ?",
        (archived_at, cutoff),
    )

    # If still over MAX_ACTIVE, archive oldest excess
    active_count = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE archived = 0"
    ).fetchone()[0]
    if active_count > MAX_ACTIVE:
        excess = active_count - MAX_ACTIVE
        conn.execute(
            "UPDATE memories SET archived = 1, archived_at = ? "
            "WHERE id IN ("
            "  SELECT id FROM memories WHERE archived = 0 AND source != 'system' "
            "  ORDER BY id ASC LIMIT ?"
            ")",
            (archived_at, excess),
        )
    conn.commit()


def _format_memories(rows, label="Shared Memory"):
    """Format memory rows into the standard string output."""
    if not rows:
        return "No memories stored yet."
    lines = [f"{label} ({len(rows)} entries):\n"]
    for row in rows:
        lines.append(f"[{row['timestamp']}] ({row['source']})")
        tags = json.loads(row["tags"])
        if tags:
            lines.append(f"  Tags: {', '.join(tags)}")
        lines.append(f"  {row['content']}")
        lines.append("")
    return "\n".join(lines)


def memory_read(last_n: int = 0) -> str:
    """Read memories. Returns all active by default, or the last N entries.

    Args:
        last_n: Number of recent entries to return (0 = all)
    """
    _migrate_from_json()
    conn = get_connection()
    if last_n > 0:
        rows = conn.execute(
            "SELECT * FROM memories WHERE archived = 0 ORDER BY id DESC LIMIT ?",
            (last_n,),
        ).fetchall()
        rows = list(reversed(rows))  # chronological order
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE archived = 0 ORDER BY id"
        ).fetchall()
    return _format_memories(rows)


def memory_write(content: str, source: str = "unknown", tags: list[str] | None = None) -> str:
    """Add a new memory entry.

    Args:
        content: The information to remember
        source: Which model/script is writing (auto-set by chat scripts)
        tags: Optional tags for categorization
    """
    _migrate_from_json()
    conn = get_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    conn.execute(
        "INSERT INTO memories (timestamp, source, content, tags) VALUES (?, ?, ?, ?)",
        (timestamp, source, content, tags_json),
    )
    conn.commit()
    _auto_archive()
    return f"Memory saved: {content[:80]}{'...' if len(content) > 80 else ''}"


def memory_search(keyword: str) -> str:
    """Search memories by keyword using FTS5.

    Args:
        keyword: Search term to look for in content and tags
    """
    _migrate_from_json()
    conn = get_connection()

    # Escape FTS5 query: wrap each word in quotes to prevent syntax errors
    words = keyword.strip().split()
    fts_query = " ".join(f'"{w}"' for w in words if w)

    if not fts_query:
        return f"No memories found matching '{keyword}'."

    rows = conn.execute(
        "SELECT m.* FROM memories m "
        "JOIN memories_fts f ON m.id = f.rowid "
        "WHERE memories_fts MATCH ? AND m.archived = 0 "
        "ORDER BY m.id",
        (fts_query,),
    ).fetchall()

    if not rows:
        return f"No memories found matching '{keyword}'."

    return _format_memories(rows, f"Found {len(rows)} memories matching '{keyword}'")


def memory_delete(index: int) -> str:
    """Delete a memory by its index (0-based, chronological order among active).

    Args:
        index: Index of the memory to delete
    """
    _migrate_from_json()
    conn = get_connection()

    # Map 0-based index to actual rowid
    row = conn.execute(
        "SELECT id, timestamp, content FROM memories "
        "WHERE archived = 0 ORDER BY id LIMIT 1 OFFSET ?",
        (index,),
    ).fetchone()

    if row is None:
        total = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE archived = 0"
        ).fetchone()[0]
        max_idx = total - 1 if total > 0 else 0
        return f"Invalid index {index}. Valid range: 0-{max_idx}"

    conn.execute("DELETE FROM memories WHERE id = ?", (row["id"],))
    conn.commit()
    return f"Memory deleted: [{row['timestamp']}] {row['content'][:80]}"


if __name__ == "__main__":
    print(memory_read())
