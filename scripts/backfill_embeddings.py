"""Backfill embeddings for all existing knowledge rows that don't have one yet.

Usage:
    cd ~/virtual-assistant
    PYTHONPATH=. python scripts/backfill_embeddings.py

Idempotent — safe to run multiple times.
After completion, create the search index in Supabase SQL Editor:
    CREATE INDEX idx_knowledge_embedding ON knowledge
      USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
"""

import os
import sys

# Load .env
from dotenv import load_dotenv
load_dotenv()

from core.db import get_supabase
from core.embeddings import embed_batch

BATCH_SIZE = 64


def main():
    db = get_supabase()

    # Fetch all knowledge rows without embeddings
    result = (
        db.table("knowledge")
        .select("id, category, key, value")
        .is_("embedding", "null")
        .execute()
    )

    rows = result.data
    if not rows:
        print("All knowledge rows already have embeddings. Nothing to do.")
        return

    print(f"Found {len(rows)} rows without embeddings. Starting backfill...")

    success = 0
    failed = 0

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        texts = [f"{r['category']}: {r['key']} — {r['value']}" for r in batch]

        vectors = embed_batch(texts)
        if not vectors:
            print(f"  Batch {i // BATCH_SIZE + 1} failed — API error")
            failed += len(batch)
            continue

        for row, vector in zip(batch, vectors):
            if vector is None:
                failed += 1
                continue
            try:
                db.table("knowledge").update({
                    "embedding": vector,
                }).eq("id", row["id"]).execute()
                success += 1
            except Exception as e:
                print(f"  Failed to update row {row['id']}: {e}")
                failed += 1

        print(f"  Batch {i // BATCH_SIZE + 1}: {len(batch)} rows processed")

    print(f"\nDone. Embedded: {success}, Failed: {failed}")
    print("\nNext step: Create the search index in Supabase SQL Editor:")
    print("  CREATE INDEX idx_knowledge_embedding ON knowledge")
    print("    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);")


if __name__ == "__main__":
    main()
