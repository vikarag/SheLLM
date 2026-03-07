"""Shared memory manager for LLM chat scripts.

Stores memories chronologically in a JSON file that all models can read/write.
"""

import json
import os
from datetime import datetime

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")


def _load() -> list[dict]:
    """Load memories from file."""
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE) as f:
        return json.load(f)


def _save(memories: list[dict]):
    """Save memories to file."""
    with open(MEMORY_FILE, "w") as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)


def memory_read(last_n: int = 0) -> str:
    """Read memories. Returns all by default, or the last N entries.

    Args:
        last_n: Number of recent entries to return (0 = all)
    """
    memories = _load()
    if not memories:
        return "No memories stored yet."

    if last_n > 0:
        memories = memories[-last_n:]

    lines = [f"Shared Memory ({len(memories)} entries):\n"]
    for m in memories:
        lines.append(f"[{m['timestamp']}] ({m['source']})")
        if m.get("tags"):
            lines.append(f"  Tags: {', '.join(m['tags'])}")
        lines.append(f"  {m['content']}")
        lines.append("")
    return "\n".join(lines)


def memory_write(content: str, source: str = "unknown", tags: list[str] | None = None) -> str:
    """Add a new memory entry.

    Args:
        content: The information to remember
        source: Which model/script is writing (auto-set by chat scripts)
        tags: Optional tags for categorization
    """
    memories = _load()
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "content": content,
        "tags": tags or [],
    }
    memories.append(entry)
    _save(memories)
    return f"Memory saved: {content[:80]}{'...' if len(content) > 80 else ''}"


def memory_search(keyword: str) -> str:
    """Search memories by keyword (case-insensitive).

    Args:
        keyword: Search term to look for in content and tags
    """
    memories = _load()
    keyword_lower = keyword.lower()
    matches = [
        m for m in memories
        if keyword_lower in m["content"].lower()
        or keyword_lower in " ".join(m.get("tags", [])).lower()
    ]
    if not matches:
        return f"No memories found matching '{keyword}'."

    lines = [f"Found {len(matches)} memories matching '{keyword}':\n"]
    for m in matches:
        lines.append(f"[{m['timestamp']}] ({m['source']})")
        if m.get("tags"):
            lines.append(f"  Tags: {', '.join(m['tags'])}")
        lines.append(f"  {m['content']}")
        lines.append("")
    return "\n".join(lines)


def memory_delete(index: int) -> str:
    """Delete a memory by its index (0-based, chronological order).

    Args:
        index: Index of the memory to delete
    """
    memories = _load()
    if index < 0 or index >= len(memories):
        return f"Invalid index {index}. Valid range: 0-{len(memories)-1}"
    removed = memories.pop(index)
    _save(memories)
    return f"Memory deleted: [{removed['timestamp']}] {removed['content'][:80]}"


if __name__ == "__main__":
    print(memory_read())
