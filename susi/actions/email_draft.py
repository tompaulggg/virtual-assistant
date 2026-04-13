"""Email draft action — creates drafts in GMX via IMAP."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SUSI_DIR = Path.home() / "Susi"


async def _email_draft(data: dict) -> str:
    from core.email_reader import EmailReader

    to = data.get("to", "").strip()
    subject = data.get("subject", "").strip()
    body = data.get("body", "").strip()
    attachment_names = data.get("attachments", [])

    if not to:
        return "Ich brauch eine Empfaenger-Adresse fuer den Entwurf."
    if not subject:
        return "Ich brauch einen Betreff."
    if not body:
        return "Ich brauch den Email-Text."

    # Resolve attachment paths from ~/Susi/
    attachment_paths = []
    if isinstance(attachment_names, list):
        for name in attachment_names:
            full_path = str(SUSI_DIR / name)
            if os.path.isfile(full_path):
                attachment_paths.append(full_path)
            else:
                # Try fuzzy search
                for root, dirs, files in os.walk(str(SUSI_DIR), followlinks=True):
                    for fname in files:
                        if name.lower() in fname.lower():
                            attachment_paths.append(os.path.join(root, fname))
                            break
                    if attachment_paths:
                        break

    reader = EmailReader()
    success = reader.create_draft(to, subject, body, attachment_paths)

    if success:
        att_text = ""
        if attachment_paths:
            att_names = [os.path.basename(p) for p in attachment_paths]
            att_text = f"\nAnhaenge: {', '.join(att_names)}"

        return (
            f"Email-Entwurf erstellt!\n"
            f"Empfaenger: {to}\n"
            f"Betreff: {subject}{att_text}\n\n"
            f"Oeffne dein Email-Programm um den Entwurf zu pruefen und abzusenden."
        )
    else:
        return "Konnte den Entwurf nicht erstellen. Sind die Email-Zugangsdaten korrekt?"


ACTIONS = [
    {
        "name": "email_draft",
        "description": "Email-Entwurf erstellen. Erstellt einen Entwurf im Email-Postfach den Thomas nur noch absenden muss. IMMER zuerst Thomas fragen bevor du den Entwurf erstellst.",
        "parameters": {
            "to": "string (Empfaenger Email-Adresse)",
            "subject": "string (Betreff)",
            "body": "string (Email-Text, professionell, deutsch)",
            "attachments": "list of strings (Dateinamen aus ~/Susi/, optional)",
        },
        "handler": _email_draft,
    },
]


def register() -> list[dict]:
    return ACTIONS
