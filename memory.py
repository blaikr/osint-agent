# ── 1. IMPORTS & SETUP ──────────────────────────────────────
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import uuid
from datetime import datetime
import chromadb
from chromadb.utils import embedding_functions


# ── 2. CHROMADB CLIENT ──────────────────────────────────────
client = chromadb.PersistentClient(path="./osint_memory")

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

collection = client.get_or_create_collection(
    name="investigations",
    embedding_function=embedding_fn,
)


# ── 3. MEMORY OPERATIONS ────────────────────────────────────
def save_investigation(subject: str, report: str, query: str) -> str:
    """Save an investigation report to long-term memory."""
    entry_id = str(uuid.uuid4())
    collection.add(
        documents=[report],
        metadatas=[{
            "subject": subject,
            "query": query,
            "timestamp": datetime.now().isoformat(),
        }],
        ids=[entry_id],
    )
    return entry_id


def search_memory(query: str, n_results: int = 3) -> str:
    """Search past investigations for relevant information."""
    results = collection.query(query_texts=[query], n_results=n_results)

    if not results["documents"] or not results["documents"][0]:
        return "No relevant past investigations found in memory."

    output = (
        "⚠️ CRITICAL INSTRUCTION TO THE AI: The text below is the ONLY information "
        "available from memory. You must quote it VERBATIM in your response. Do NOT "
        "add dates, URLs, or facts that are not shown below. Do NOT paraphrase. If "
        "the user asks about a subject not shown below, say \"I have no memory of "
        f"that subject.\"\n\nFound {len(results['documents'][0])} relevant past investigations:\n\n"
    )

    for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
        output += f"--- Past Investigation {i} ---\n"
        output += f"Subject: {metadata.get('subject', 'Unknown')}\n"
        output += f"Original Query: {metadata.get('query', 'Unknown')}\n"
        output += f"Date: {metadata.get('timestamp', 'Unknown')[:10]}\n"
        output += f"Report excerpt:\n{doc[:1500]}...\n\n"

    return output


def list_all_subjects() -> str:
    """List everything the agent has ever investigated."""
    results = collection.get()
    if not results["metadatas"]:
        return "Memory is empty. No past investigations."

    subjects = [
        {"subject": m.get("subject", "Unknown"), "timestamp": m.get("timestamp", "Unknown")[:10]}
        for m in results["metadatas"]
    ]
    subjects.sort(key=lambda x: x["timestamp"], reverse=True)

    output = f"Past investigations ({len(subjects)} total):\n"
    for s in subjects:
        output += f"  - {s['subject']} (investigated {s['timestamp']})\n"
    return output
