"""Ingest documents from ~/Susi/ into Supabase Knowledge Store."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SUSI_DIR = Path.home() / "Susi"
MANIFEST_FILE = SUSI_DIR / ".file_manifest.json"
MAX_INGEST_SIZE = 10 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".html", ".csv"}
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def _load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_manifest(manifest: dict):
    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _extract_text(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
        except Exception as e:
            logger.error(f"PDF extraction failed for {filepath}: {e}")
            return ""

    elif ext in (".txt", ".md", ".csv", ".html"):
        try:
            text = Path(filepath).read_text(encoding="utf-8", errors="replace")
            if ext == ".html":
                import re
                text = re.sub(r"<[^>]+>", " ", text)
            return text
        except Exception as e:
            logger.error(f"Text extraction failed for {filepath}: {e}")
            return ""

    return ""


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    if len(words) <= CHUNK_SIZE:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    while start < len(words):
        end = start + CHUNK_SIZE
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start = end - CHUNK_OVERLAP

    return chunks


async def ingest_all(memory, user_id: str) -> str:
    if not SUSI_DIR.exists():
        return "~/Susi/ existiert nicht."

    manifest = _load_manifest()
    ingested = 0
    skipped = 0
    errors = 0

    for root, dirs, files in os.walk(str(SUSI_DIR), followlinks=True):
        for fname in files:
            if fname.startswith("."):
                continue

            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, str(SUSI_DIR))

            size = os.path.getsize(full_path)
            if size > MAX_INGEST_SIZE:
                logger.warning(f"Skipping {rel_path}: too large ({size / 1024 / 1024:.1f} MB)")
                skipped += 1
                continue

            modified = os.path.getmtime(full_path)
            modified_str = datetime.fromtimestamp(modified).isoformat()
            prev = manifest.get(rel_path, {})
            if prev.get("modified") == modified_str and prev.get("size") == size:
                skipped += 1
                continue

            text = _extract_text(full_path)
            if not text:
                errors += 1
                continue

            chunks = _chunk_text(text)
            if not chunks:
                skipped += 1
                continue

            # Delete old chunks
            for i in range(prev.get("chunks", 0)):
                memory.delete_knowledge(user_id, "dokument", f"{rel_path}:chunk_{i}")

            # Store new chunks
            for i, chunk in enumerate(chunks):
                memory.store_knowledge(user_id, "dokument", f"{rel_path}:chunk_{i}", chunk)

            manifest[rel_path] = {
                "modified": modified_str,
                "size": size,
                "chunks": len(chunks),
            }
            ingested += 1
            logger.info(f"Ingested {rel_path}: {len(chunks)} chunks")

    # Clean deleted files
    for rel_path in list(manifest.keys()):
        full_path = os.path.join(str(SUSI_DIR), rel_path)
        if not os.path.exists(full_path):
            for i in range(manifest[rel_path].get("chunks", 0)):
                memory.delete_knowledge(user_id, "dokument", f"{rel_path}:chunk_{i}")
            del manifest[rel_path]
            logger.info(f"Removed deleted file: {rel_path}")

    _save_manifest(manifest)
    return f"Ingestion fertig: {ingested} neu, {skipped} unveraendert, {errors} Fehler."


async def _file_ingest_action(data: dict) -> str:
    from core.memory import Memory
    user_id = data.get("user_id", "")
    memory = Memory(bot_name="susi")
    return await ingest_all(memory, user_id)


ACTIONS = [
    {
        "name": "file_ingest",
        "description": "Dateien aus ~/Susi/ einlesen und als Wissen speichern. Nutze das wenn Thomas sagt 'lies die Dateien ein' oder nach dem ersten Setup.",
        "parameters": {},
        "handler": _file_ingest_action,
    },
]


def register() -> list[dict]:
    return ACTIONS
