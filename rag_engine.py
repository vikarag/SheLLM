"""RAG engine for shellm — index, search, list, and delete documents with embeddings."""

import json
import os
import time

import numpy as np
from openai import OpenAI

RAG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_store")
INDEX_FILE = os.path.join(RAG_DIR, "index.json")
CHUNKS_FILE = os.path.join(RAG_DIR, "chunks.json")
EMBEDDINGS_FILE = os.path.join(RAG_DIR, "embeddings.npy")

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


def _ensure_dir():
    os.makedirs(RAG_DIR, exist_ok=True)


def _load_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE) as f:
            return json.load(f)
    return []


def _save_index(index):
    _ensure_dir()
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _load_chunks():
    if os.path.exists(CHUNKS_FILE):
        with open(CHUNKS_FILE) as f:
            return json.load(f)
    return []


def _save_chunks(chunks):
    _ensure_dir()
    with open(CHUNKS_FILE, "w") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


def _load_embeddings():
    if os.path.exists(EMBEDDINGS_FILE):
        return np.load(EMBEDDINGS_FILE)
    return np.empty((0, EMBED_DIM), dtype=np.float32)


def _save_embeddings(embs):
    _ensure_dir()
    np.save(EMBEDDINGS_FILE, embs)


def _chunk_text(text, chunk_size=800, overlap=100):
    """Split text into chunks at paragraph boundaries, then sentence boundaries."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # If adding this paragraph exceeds chunk_size, finalize current
        if current and len(current) + len(para) + 2 > chunk_size:
            chunks.append(current.strip())
            # Keep overlap from end of current chunk
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    # If any chunk is still too long, split at sentence boundaries
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
    import re
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
    # Normalize
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    matrix_norm = matrix / norms
    return matrix_norm @ query_norm


# ── Public API ────────────────────────────────────────────────────────


def rag_index(text, filename="untitled", tags=None):
    """Chunk text, embed, and store in the RAG index."""
    chunks_text = _chunk_text(text)
    if not chunks_text:
        return "No text to index."

    # Generate doc_id
    index = _load_index()
    doc_id = f"doc_{int(time.time())}_{len(index)}"

    # Embed all chunks
    embeddings = _embed(chunks_text)

    # Load existing data
    existing_chunks = _load_chunks()
    existing_embs = _load_embeddings()

    # Append new chunks
    for i, chunk in enumerate(chunks_text):
        existing_chunks.append({
            "doc_id": doc_id,
            "chunk_index": i,
            "text": chunk,
        })

    # Append embeddings
    if existing_embs.shape[0] > 0:
        all_embs = np.vstack([existing_embs, embeddings])
    else:
        all_embs = embeddings

    # Update index
    index.append({
        "doc_id": doc_id,
        "filename": filename,
        "chunk_count": len(chunks_text),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tags": tags or [],
    })

    _save_index(index)
    _save_chunks(existing_chunks)
    _save_embeddings(all_embs)

    return f"Indexed '{filename}' as {doc_id}: {len(chunks_text)} chunks, {len(text)} chars"


def rag_search(query, top_k=5):
    """Search the RAG index by semantic similarity."""
    chunks = _load_chunks()
    embs = _load_embeddings()

    if not chunks or embs.shape[0] == 0:
        return "RAG index is empty. Index some documents first."

    query_emb = _embed([query])[0]
    scores = _cosine_similarity(query_emb, embs)

    # Get top-k indices
    k = min(top_k, len(scores))
    top_indices = np.argsort(scores)[-k:][::-1]

    index = _load_index()
    doc_map = {d["doc_id"]: d["filename"] for d in index}

    results = []
    for idx in top_indices:
        chunk = chunks[idx]
        score = float(scores[idx])
        if score < 0.1:
            continue
        filename = doc_map.get(chunk["doc_id"], "unknown")
        results.append(
            f"[{score:.3f}] {filename} (chunk {chunk['chunk_index']}):\n{chunk['text']}"
        )

    if not results:
        return "No relevant results found."

    return f"RAG Search: {len(results)} results for '{query}'\n\n" + "\n\n---\n\n".join(results)


def rag_list():
    """List all indexed documents."""
    index = _load_index()
    if not index:
        return "RAG index is empty."

    lines = [f"Indexed documents ({len(index)}):\n"]
    for doc in index:
        tags = ", ".join(doc.get("tags", [])) if doc.get("tags") else "none"
        lines.append(
            f"  {doc['doc_id']}: {doc['filename']} "
            f"({doc['chunk_count']} chunks, {doc['timestamp']}, tags: {tags})"
        )
    return "\n".join(lines)


def rag_delete(doc_id):
    """Delete a document from the RAG index by doc_id."""
    index = _load_index()
    chunks = _load_chunks()
    embs = _load_embeddings()

    # Find the doc
    doc_entry = None
    for d in index:
        if d["doc_id"] == doc_id:
            doc_entry = d
            break

    if not doc_entry:
        return f"Document not found: {doc_id}"

    filename = doc_entry["filename"]

    # Filter out chunks and corresponding embeddings
    keep_indices = []
    new_chunks = []
    for i, chunk in enumerate(chunks):
        if chunk["doc_id"] != doc_id:
            keep_indices.append(i)
            new_chunks.append(chunk)

    # Rebuild embeddings
    if keep_indices and embs.shape[0] > 0:
        new_embs = embs[keep_indices]
    else:
        new_embs = np.empty((0, EMBED_DIM), dtype=np.float32)

    # Remove from index
    new_index = [d for d in index if d["doc_id"] != doc_id]

    _save_index(new_index)
    _save_chunks(new_chunks)
    _save_embeddings(new_embs)

    return f"Deleted '{filename}' ({doc_id})"
