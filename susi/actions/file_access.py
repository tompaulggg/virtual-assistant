"""File access actions — search, send, and ingest files from ~/Susi/."""

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SUSI_DIR = Path.home() / "Susi"

ALLOWED_ROOTS = [
    str(Path.home() / "Susi"),
    str(Path.home() / "Documents" / "Businessplan"),
    str(Path.home() / "Documents" / "BotProjects" / "docs"),
    str(Path.home() / "Documents" / "BotProjects" / "sops"),
]


def _is_safe_path(filepath: str) -> bool:
    real = os.path.realpath(filepath)
    return any(real.startswith(root) for root in ALLOWED_ROOTS)


def _fuzzy_match(query: str, filename: str) -> bool:
    q_lower = query.lower()
    f_lower = filename.lower()
    return all(word in f_lower for word in q_lower.split())


async def _file_search(data: dict) -> str:
    query = data.get("query", "").strip()
    if not query:
        return "Ich brauch einen Suchbegriff fuer die Dateisuche."

    if not SUSI_DIR.exists():
        return "Der Susi-Ordner (~/Susi/) existiert nicht. Bitte zuerst einrichten."

    matches = []
    for root, dirs, files in os.walk(str(SUSI_DIR), followlinks=True):
        for fname in files:
            if fname.startswith("."):
                continue
            full_path = os.path.join(root, fname)
            if not _is_safe_path(full_path):
                continue
            if _fuzzy_match(query, fname):
                rel = os.path.relpath(full_path, str(SUSI_DIR))
                stat = os.stat(full_path)
                size_kb = stat.st_size / 1024
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y")
                matches.append({
                    "name": fname,
                    "path": rel,
                    "full_path": full_path,
                    "size": f"{size_kb:.0f} KB",
                    "modified": modified,
                })

    if not matches:
        return f"Keine Dateien gefunden fuer '{query}' in ~/Susi/."

    matches.sort(key=lambda m: len(m["name"]))

    lines = [f"Gefunden ({len(matches)} Dateien):\n"]
    for m in matches[:10]:
        lines.append(f"  {m['path']} ({m['size']}, {m['modified']})")

    return "\n".join(lines)


async def _file_send(data: dict) -> str | dict:
    filename = data.get("filename", "").strip()
    if not filename:
        return "Welche Datei soll ich senden?"

    full_path = str(SUSI_DIR / filename)
    if not os.path.isfile(full_path):
        for root, dirs, files in os.walk(str(SUSI_DIR), followlinks=True):
            for fname in files:
                if _fuzzy_match(filename, fname):
                    full_path = os.path.join(root, fname)
                    break

    if not os.path.isfile(full_path):
        return f"Datei nicht gefunden: {filename}"

    if not _is_safe_path(full_path):
        return "Zugriff auf diese Datei ist nicht erlaubt."

    size_mb = os.path.getsize(full_path) / (1024 * 1024)
    if size_mb > 50:
        return f"Datei ist zu gross ({size_mb:.1f} MB, max 50 MB)."

    return {"type": "send_file", "path": full_path}


ACTIONS = [
    {
        "name": "file_search",
        "description": "Dateien in ~/Susi/ suchen. Nutze das wenn Thomas nach einem Dokument fragt.",
        "parameters": {"query": "string (Suchbegriff, z.B. 'Businessplan' oder 'Lebenslauf')"},
        "handler": _file_search,
    },
    {
        "name": "file_send",
        "description": "Datei aus ~/Susi/ als Telegram-Dokument an Thomas senden.",
        "parameters": {"filename": "string (Dateiname oder Pfad in ~/Susi/)"},
        "handler": _file_send,
    },
]


def register() -> list[dict]:
    return ACTIONS
