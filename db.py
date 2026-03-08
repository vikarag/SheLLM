"""Shared SQLite database module for SheLLM memory and RAG.

Provides thread-local connections (critical for Telegram's asyncio.to_thread()),
WAL mode for concurrent reads, and idempotent schema creation.
"""

import os
import sqlite3
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shellm.db")

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection with WAL mode and foreign keys."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
        _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    """Create all tables and FTS indexes if they don't exist."""
    conn.executescript("""
        -- Memory tables
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'unknown',
            content TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]',
            archived INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT DEFAULT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, tags, content='memories', content_rowid='id'
        );

        -- FTS sync triggers for memories
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, tags)
            VALUES (new.id, new.content, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, tags)
            VALUES ('delete', old.id, old.content, old.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, tags)
            VALUES ('delete', old.id, old.content, old.tags);
            INSERT INTO memories_fts(rowid, content, tags)
            VALUES (new.id, new.content, new.tags);
        END;

        -- RAG tables
        CREATE TABLE IF NOT EXISTS rag_docs (
            doc_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            chunk_count INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS rag_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL REFERENCES rag_docs(doc_id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
            text, content='rag_chunks', content_rowid='id'
        );

        -- FTS sync triggers for rag_chunks
        CREATE TRIGGER IF NOT EXISTS rag_chunks_ai AFTER INSERT ON rag_chunks BEGIN
            INSERT INTO rag_chunks_fts(rowid, text) VALUES (new.id, new.text);
        END;

        CREATE TRIGGER IF NOT EXISTS rag_chunks_ad AFTER DELETE ON rag_chunks BEGIN
            INSERT INTO rag_chunks_fts(rag_chunks_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
        END;

        CREATE TRIGGER IF NOT EXISTS rag_chunks_au AFTER UPDATE ON rag_chunks BEGIN
            INSERT INTO rag_chunks_fts(rag_chunks_fts, rowid, text)
            VALUES ('delete', old.id, old.text);
            INSERT INTO rag_chunks_fts(rowid, text) VALUES (new.id, new.text);
        END;
    """)
    conn.commit()
