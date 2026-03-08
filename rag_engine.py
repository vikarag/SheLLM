"""RAG engine for shellm — index, search, list, and delete documents with hybrid search.

Uses SQLite for storage with FTS5 for keyword matching combined with
cosine similarity on embeddings for hybrid semantic+keyword search.
"""

import json
import os
import re
import time

import numpy as np
from openai import OpenAI

from db import get_connection

_RAG_STORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_store")

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

_client = None


def _get_client():
    global _client
    if _client is None:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    return _client


def _migrate_from_rag_store():
    """One-time migration from rag_store/ directory to SQLite."""
    if not os.path.isdir(_RAG_STORE_DIR):
        return
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM rag_docs").fetchone()[0]
    if count > 0:
        return

    index_file = os.path.join(_RAG_STORE_DIR, "index.json")
    chunks_file = os.path.join(_RAG_STORE_DIR, "chunks.json")
    embeddings_file = os.path.join(_RAG_STORE_DIR, "embeddings.npy")

    if not os.path.exists(index_file):
        return

    try:
        with open(index_file) as f:
            index = json.load(f)
        with open(chunks_file) as f:
            chunks = json.load(f)
        embeddings = np.load(embeddings_file) if os.path.exists(embeddings_file) else np.empty((0, EMBED_DIM), dtype=np.float32)

        for doc in index:
            conn.execute(
                "INSERT INTO rag_docs (doc_id, filename, chunk_count, timestamp, tags) VALUES (?, ?, ?, ?, ?)",
                (doc["doc_id"], doc["filename"], doc["chunk_count"], doc["timestamp"],
                 json.dumps(doc.get("tags", []), ensure_ascii=False)),
            )

        for i, chunk in enumerate(chunks):
            emb_blob = embeddings[i].tobytes() if i < len(embeddings) else np.zeros(EMBED_DIM, dtype=np.float32).tobytes()
            conn.execute(
                "INSERT INTO rag_chunks (doc_id, chunk_index, text, embedding) VALUES (?, ?, ?, ?)",
                (chunk["doc_id"], chunk["chunk_index"], chunk["text"], emb_blob),
            )

        conn.commit()
        os.rename(_RAG_STORE_DIR, _RAG_STORE_DIR + ".bak")
    except Exception:
        conn.rollback()


def _chunk_text(text, chunk_size=800, overlap=100):
    """Split text into chunks at paragraph boundaries, then sentence boundaries."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 2 > chunk_size:
            chunks.append(current.strip())
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    final = []
    for chunk in chunks:
        if len(chunk) <= chunk_size * 1.5:
            final.append(chunk)
        else:
            sentences = _split_sentences(chunk)
            buf = ""
            for sent in sentences:
                if buf and len(buf) + len(sent) + 1 > chunk_size:
                    final.append(buf.strip())
                    buf = sent
                else:
                    buf = buf + " " + sent if buf else sent
            if buf.strip():
                final.append(buf.strip())

    return final if final else [text[:chunk_size]]


def _split_sentences(text):
    """Split text into sentences (simple heuristic)."""
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p for p in parts if p.strip()]


def _embed(texts):
    """Get embeddings for a list of texts."""
    client = _get_client()
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return np.array([d.embedding for d in response.data], dtype=np.float32)


def _cosine_similarity(query_vec, matrix):
    """Compute cosine similarity between a query vector and a matrix of vectors."""
    if matrix.shape[0] == 0:
        return np.array([])
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    matrix_norm = matrix / norms
    return matrix_norm @ query_norm


# ── Public API ────────────────────────────────────────────────────────


def rag_index(text, filename="untitled", tags=None):
    """Chunk text, embed, and store in the RAG index."""
    _migrate_from_rag_store()
    chunks_text = _chunk_text(text)
    if not chunks_text:
        return "No text to index."

    conn = get_connection()
    doc_count = conn.execute("SELECT COUNT(*) FROM rag_docs").fetchone()[0]
    doc_id = f"doc_{int(time.time())}_{doc_count}"

    # Embed all chunks
    embeddings = _embed(chunks_text)

    # Insert doc record
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    conn.execute(
        "INSERT INTO rag_docs (doc_id, filename, chunk_count, timestamp, tags) VALUES (?, ?, ?, ?, ?)",
        (doc_id, filename, len(chunks_text), time.strftime("%Y-%m-%d %H:%M:%S"), tags_json),
    )

    # Insert chunks with embeddings as BLOBs
    for i, chunk in enumerate(chunks_text):
        conn.execute(
            "INSERT INTO rag_chunks (doc_id, chunk_index, text, embedding) VALUES (?, ?, ?, ?)",
            (doc_id, i, chunk, embeddings[i].tobytes()),
        )

    conn.commit()
    return f"Indexed '{filename}' as {doc_id}: {len(chunks_text)} chunks, {len(text)} chars"


def rag_search(query, top_k=5):
    """Search the RAG index using hybrid semantic + keyword search."""
    _migrate_from_rag_store()
    conn = get_connection()

    rows = conn.execute("SELECT id, doc_id, chunk_index, text, embedding FROM rag_chunks").fetchall()
    if not rows:
        return "RAG index is empty. Index some documents first."

    # --- Cosine similarity scores ---
    chunk_ids = [r["id"] for r in rows]
    texts = [r["text"] for r in rows]
    embeddings = np.array(
        [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]
    )

    query_emb = _embed([query])[0]
    cosine_scores = _cosine_similarity(query_emb, embeddings)

    # --- FTS5 BM25 scores ---
    words = query.strip().split()
    fts_query = " ".join(f'"{w}"' for w in words if w)

    bm25_map = {}
    if fts_query:
        try:
            fts_rows = conn.execute(
                "SELECT rowid, rank FROM rag_chunks_fts WHERE rag_chunks_fts MATCH ? ORDER BY rank",
                (fts_query,),
            ).fetchall()
            if fts_rows:
                # rank is negative (lower = better match), normalize to 0-1
                raw_scores = {r["rowid"]: -r["rank"] for r in fts_rows}
                max_score = max(raw_scores.values()) if raw_scores else 1.0
                if max_score > 0:
                    bm25_map = {rid: s / max_score for rid, s in raw_scores.items()}
        except Exception:
            pass  # FTS query might fail on unusual input; fall back to cosine only

    # --- Combine scores ---
    combined = []
    doc_map = {}
    for doc_row in conn.execute("SELECT doc_id, filename FROM rag_docs").fetchall():
        doc_map[doc_row["doc_id"]] = doc_row["filename"]

    for i, row in enumerate(rows):
        cos = float(cosine_scores[i])
        bm25 = bm25_map.get(row["id"], 0.0)
        score = 0.7 * cos + 0.3 * bm25
        combined.append((score, cos, bm25, row))

    combined.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, cos, bm25, row in combined[:top_k]:
        if score < 0.1:
            continue
        filename = doc_map.get(row["doc_id"], "unknown")
        results.append(
            f"[{score:.3f}] {filename} (chunk {row['chunk_index']}):\n{row['text']}"
        )

    if not results:
        return "No relevant results found."

    return f"RAG Search: {len(results)} results for '{query}'\n\n" + "\n\n---\n\n".join(results)


def rag_list():
    """List all indexed documents."""
    _migrate_from_rag_store()
    conn = get_connection()
    docs = conn.execute("SELECT * FROM rag_docs ORDER BY timestamp").fetchall()

    if not docs:
        return "RAG index is empty."

    lines = [f"Indexed documents ({len(docs)}):\n"]
    for doc in docs:
        tags = json.loads(doc["tags"])
        tags_str = ", ".join(tags) if tags else "none"
        lines.append(
            f"  {doc['doc_id']}: {doc['filename']} "
            f"({doc['chunk_count']} chunks, {doc['timestamp']}, tags: {tags_str})"
        )
    return "\n".join(lines)


def rag_delete(doc_id):
    """Delete a document from the RAG index by doc_id."""
    _migrate_from_rag_store()
    conn = get_connection()

    doc = conn.execute("SELECT filename FROM rag_docs WHERE doc_id = ?", (doc_id,)).fetchone()
    if not doc:
        return f"Document not found: {doc_id}"

    filename = doc["filename"]
    conn.execute("DELETE FROM rag_docs WHERE doc_id = ?", (doc_id,))
    conn.commit()
    return f"Deleted '{filename}' ({doc_id})"
