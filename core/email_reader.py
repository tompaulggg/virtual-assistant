"""Email reader — IMAP read-only, extracts facts from emails."""

import os
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import logging
import json
import anthropic

logger = logging.getLogger(__name__)


class EmailReader:
    def __init__(self):
        self.server = os.getenv("GMX_IMAP_SERVER", "imap.gmx.net")
        self.email_addr = os.getenv("GMX_EMAIL", "")
        self.password = os.getenv("GMX_PASSWORD", "")
        self.client = anthropic.Anthropic(
            api_key=os.getenv("SUSI_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        )

    def _decode_header_value(self, value):
        """Decode email header (handles encoded words)."""
        if not value:
            return ""
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)

    def _extract_body(self, msg) -> str:
        """Extract plain text body from email message."""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        return part.get_payload(decode=True).decode(charset, errors="replace")
                    except Exception:
                        continue
            # Fallback to HTML if no plain text
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        html = part.get_payload(decode=True).decode(charset, errors="replace")
                        # Strip HTML tags roughly
                        import re
                        return re.sub(r'<[^>]+>', ' ', html)[:3000]
                    except Exception:
                        continue
        else:
            try:
                charset = msg.get_content_charset() or "utf-8"
                return msg.get_payload(decode=True).decode(charset, errors="replace")
            except Exception:
                return ""
        return ""

    def fetch_recent(self, hours: int = 6, max_emails: int = 20) -> list[dict]:
        """Fetch recent emails via IMAP. Returns list of {from, subject, date, body}."""
        if not self.email_addr or not self.password:
            logger.warning("Email credentials not configured")
            return []

        try:
            mail = imaplib.IMAP4_SSL(self.server, 993)
            mail.login(self.email_addr, self.password)
            mail.select("INBOX", readonly=True)

            # Search for recent emails
            since_date = (datetime.now() - timedelta(hours=hours)).strftime("%d-%b-%Y")
            _, message_ids = mail.search(None, f'(SINCE "{since_date}")')

            if not message_ids[0]:
                mail.logout()
                return []

            ids = message_ids[0].split()[-max_emails:]  # Last N
            emails = []

            for eid in ids:
                _, msg_data = mail.fetch(eid, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue

                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                sender = self._decode_header_value(msg.get("From", ""))
                subject = self._decode_header_value(msg.get("Subject", ""))
                date_str = msg.get("Date", "")
                body = self._extract_body(msg)[:2000]  # Cap body

                emails.append({
                    "from": sender,
                    "subject": subject,
                    "date": date_str,
                    "body": body,
                })

            mail.logout()
            logger.info(f"Fetched {len(emails)} emails from last {hours}h")
            return emails

        except Exception as e:
            logger.error(f"IMAP error: {e}")
            return []

    def extract_facts(self, emails: list[dict]) -> list[dict]:
        """Use Haiku to extract facts from a batch of emails."""
        if not emails:
            return []

        # Build a summary of emails for extraction
        email_texts = []
        for e in emails[:10]:  # Max 10 at a time
            email_texts.append(
                f"Von: {e['from']}\n"
                f"Betreff: {e['subject']}\n"
                f"Datum: {e['date']}\n"
                f"Inhalt: {e['body'][:500]}"
            )

        combined = "\n\n---\n\n".join(email_texts)

        try:
            extraction = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=(
                    "Du extrahierst Fakten aus E-Mails. "
                    "Antworte NUR mit einem JSON-Array von Objekten, oder mit [] wenn nichts Relevantes.\n"
                    "Jedes Objekt: {\"category\": \"...\", \"key\": \"...\", \"value\": \"...\"}\n\n"
                    "Kategorien:\n"
                    "- person (Name, Rolle, Beziehung, Kontaktinfos aus der E-Mail)\n"
                    "- firma (Firmenname, Branche, Infos)\n"
                    "- termin (Termine, Deadlines, Fristen aus E-Mails)\n"
                    "- abmachung (Vereinbarungen, Zusagen, offene Punkte)\n"
                    "- kontakt (E-Mail-Adressen, Telefonnummern)\n"
                    "- finanzen (Rechnungen, Beträge, Zahlungen)\n"
                    "- notiz (alles andere Wichtige)\n\n"
                    "Extrahiere NUR echte Fakten. Ignoriere Newsletter, Spam, Werbung. "
                    "Key = kurzer Bezeichner, Value = die konkrete Info inkl. Datum wenn relevant."
                ),
                messages=[{
                    "role": "user",
                    "content": f"Extrahiere Fakten aus diesen E-Mails:\n\n{combined}",
                }],
            )

            text = extraction.content[0].text.strip()
            if text.startswith("["):
                facts = json.loads(text)
                return [f for f in facts if all(k in f for k in ("category", "key", "value"))]
        except Exception as e:
            logger.error(f"Email fact extraction failed: {e}")

        return []

    async def sync_and_learn(self, user_id: str, memory, hours: int = 6) -> str:
        """Fetch recent emails, extract facts, store in knowledge."""
        emails = self.fetch_recent(hours=hours)
        if not emails:
            return "Keine neuen E-Mails gefunden."

        facts = self.extract_facts(emails)
        stored = 0
        for fact in facts:
            memory.store_knowledge(user_id, fact["category"], fact["key"], fact["value"])
            stored += 1

        summary = f"{len(emails)} E-Mails gelesen, {stored} Fakten gelernt."
        logger.info(f"Email sync: {summary}")
        return summary

    def scan_inbox(self, max_emails: int = 500) -> dict:
        """Scan entire inbox and categorize senders by frequency."""
        if not self.email_addr or not self.password:
            return {"error": "Email credentials not configured"}

        try:
            mail = imaplib.IMAP4_SSL(self.server, 993)
            mail.login(self.email_addr, self.password)
            mail.select("INBOX", readonly=True)

            _, message_ids = mail.search(None, "ALL")
            if not message_ids[0]:
                mail.logout()
                return {"total": 0, "senders": {}}

            all_ids = message_ids[0].split()
            total = len(all_ids)
            # Sample last N emails for analysis
            sample_ids = all_ids[-max_emails:]

            sender_counts: dict[str, int] = {}
            for eid in sample_ids:
                try:
                    _, msg_data = mail.fetch(eid, "(BODY[HEADER.FIELDS (FROM)])")
                    if msg_data and msg_data[0]:
                        raw_from = msg_data[0][1]
                        if isinstance(raw_from, bytes):
                            raw_from = raw_from.decode("utf-8", errors="replace")
                        # Extract email address
                        import re
                        match = re.search(r'[\w.+-]+@[\w.-]+', raw_from)
                        if match:
                            addr = match.group().lower()
                            sender_counts[addr] = sender_counts.get(addr, 0) + 1
                except Exception:
                    continue

            mail.logout()

            # Sort by frequency
            sorted_senders = sorted(sender_counts.items(), key=lambda x: -x[1])
            return {
                "total": total,
                "sampled": len(sample_ids),
                "unique_senders": len(sender_counts),
                "top_senders": sorted_senders[:30],
            }

        except Exception as e:
            logger.error(f"Inbox scan error: {e}")
            return {"error": str(e)}

    def delete_from_sender(self, sender_email: str) -> int:
        """Move all emails from a sender to trash. Returns count deleted."""
        if not self.email_addr or not self.password:
            return 0

        try:
            mail = imaplib.IMAP4_SSL(self.server, 993)
            mail.login(self.email_addr, self.password)
            mail.select("INBOX", readonly=False)  # Write access

            _, message_ids = mail.search(None, f'(FROM "{sender_email}")')
            if not message_ids[0]:
                mail.logout()
                return 0

            ids = message_ids[0].split()
            for eid in ids:
                # Mark as deleted
                mail.store(eid, "+FLAGS", "\\Deleted")

            mail.expunge()
            mail.logout()
            logger.info(f"Deleted {len(ids)} emails from {sender_email}")
            return len(ids)

        except Exception as e:
            logger.error(f"Delete error: {e}")
            return 0

    def find_unsubscribe_links(self, sender_email: str, max_check: int = 3) -> list[str]:
        """Find unsubscribe links in emails from a sender."""
        if not self.email_addr or not self.password:
            return []

        try:
            mail = imaplib.IMAP4_SSL(self.server, 993)
            mail.login(self.email_addr, self.password)
            mail.select("INBOX", readonly=True)

            _, message_ids = mail.search(None, f'(FROM "{sender_email}")')
            if not message_ids[0]:
                mail.logout()
                return []

            ids = message_ids[0].split()[-max_check:]
            links = set()

            import re
            for eid in ids:
                try:
                    _, msg_data = mail.fetch(eid, "(RFC822)")
                    if not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    # Check List-Unsubscribe header
                    unsub_header = msg.get("List-Unsubscribe", "")
                    if unsub_header:
                        for match in re.finditer(r'<(https?://[^>]+)>', unsub_header):
                            links.add(match.group(1))

                    # Check body for unsubscribe links
                    body = self._extract_body(msg)
                    for match in re.finditer(
                        r'(https?://\S*(?:unsubscribe|abmelden|abbestellen|opt.?out)\S*)',
                        body, re.IGNORECASE
                    ):
                        links.add(match.group(1))

                except Exception:
                    continue

            mail.logout()
            return list(links)[:5]

        except Exception as e:
            logger.error(f"Unsubscribe search error: {e}")
            return []

    def classify_importance(self, emails: list[dict]) -> list[dict]:
        """Classify emails as important/newsletter/spam using Haiku."""
        if not emails:
            return []

        email_texts = []
        for i, e in enumerate(emails[:15]):
            email_texts.append(
                f"[{i}] Von: {e['from']}\n"
                f"Betreff: {e['subject']}\n"
                f"Anfang: {e['body'][:200]}"
            )

        combined = "\n\n".join(email_texts)

        try:
            result = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=(
                    "Klassifiziere E-Mails. Antworte NUR mit JSON-Array.\n"
                    "Jedes Objekt: {\"index\": N, \"type\": \"wichtig|newsletter|spam|info\", \"reason\": \"kurzer Grund\"}\n"
                    "wichtig = persönliche Mail, Rechnung, Termin, Vertrag, Behörde\n"
                    "newsletter = regelmäßiger Versand, Abo\n"
                    "spam = Werbung, Promotion\n"
                    "info = automatische Benachrichtigung (Versand, Login, etc.)"
                ),
                messages=[{
                    "role": "user",
                    "content": f"Klassifiziere:\n\n{combined}",
                }],
            )

            text = result.content[0].text.strip()
            if text.startswith("["):
                classifications = json.loads(text)
                # Merge back into emails
                for c in classifications:
                    idx = c.get("index", -1)
                    if 0 <= idx < len(emails):
                        emails[idx]["type"] = c.get("type", "info")
                        emails[idx]["reason"] = c.get("reason", "")
                return emails
        except Exception as e:
            logger.error(f"Classification failed: {e}")

        return emails
