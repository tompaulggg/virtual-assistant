import os
import io
import time
import logging
import tempfile
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from core.brain import Brain
from core.types import AssistantConfig

logger = logging.getLogger(__name__)


def is_authorized(user_id: str, allowed_ids: list[str]) -> bool:
    return user_id in allowed_ids


class RateLimiter:
    def __init__(self, max_per_minute: int = 20):
        self.max_per_minute = max_per_minute
        self.requests: dict[str, list[float]] = {}

    def check(self, user_id: str) -> bool:
        now = time.time()
        if user_id not in self.requests:
            self.requests[user_id] = []

        # Remove requests older than 60 seconds
        self.requests[user_id] = [
            t for t in self.requests[user_id] if now - t < 60
        ]

        if len(self.requests[user_id]) >= self.max_per_minute:
            return False

        self.requests[user_id].append(now)
        return True


def sanitize_input(text: str, max_length: int = 4000) -> str:
    """Remove control characters (except newlines) and cap length."""
    cleaned = "".join(c for c in text if c == "\n" or c.isprintable())
    return cleaned[:max_length]


class Bot:
    def __init__(self, brain: Brain, config: AssistantConfig):
        self.brain = brain
        self.config = config
        self.allowed_ids = os.getenv(config.allowed_user_ids_env, "").split(",")
        self.rate_limiter = RateLimiter(max_per_minute=20)
        self._app = ApplicationBuilder().token(os.getenv(config.token_env)).build()

    def get_application(self):
        """Return the Telegram Application instance (needed by the scheduler)."""
        return self._app

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        if not is_authorized(user_id, self.allowed_ids):
            await update.message.reply_text(
                "Hallo! Ich bin leider nur für bestimmte Personen verfügbar."
            )
            return

        await update.message.reply_text(
            f"Hey {self.config.user_name}! Ich bin {self.config.name}.\n\n"
            f"{self.config.greeting}"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)

        if not is_authorized(user_id, self.allowed_ids):
            await update.message.reply_text(
                "Hallo! Ich bin leider nur für bestimmte Personen verfügbar."
            )
            return

        if not self.rate_limiter.check(user_id):
            await update.message.reply_text(
                "Du sendest gerade sehr viele Nachrichten. Warte kurz."
            )
            return

        text = sanitize_input(update.message.text)
        await update.message.chat.send_action("typing")

        try:
            response = await self.brain.process(text, user_id)
        except Exception as e:
            logger.error(f"Brain error: {e}")
            response = (
                "Ich hab gerade ein technisches Problem, "
                "versuch's in ein paar Minuten nochmal."
            )

        # Handle special return types (e.g. file_send)
        if isinstance(response, dict) and response.get("type") == "send_file":
            try:
                await update.message.reply_document(
                    document=open(response["path"], "rb"),
                    filename=os.path.basename(response["path"]),
                )
            except Exception as e:
                logger.error(f"File send error: {e}")
                await update.message.reply_text(f"Konnte Datei nicht senden: {e}")
            return

        await update.message.reply_text(response)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)

        if not is_authorized(user_id, self.allowed_ids):
            await update.message.reply_text(
                "Hallo! Ich bin leider nur für bestimmte Personen verfügbar."
            )
            return

        if not self.rate_limiter.check(user_id):
            await update.message.reply_text(
                "Du sendest gerade sehr viele Nachrichten. Warte kurz."
            )
            return

        doc = update.message.document
        file_name = doc.file_name or "dokument"
        mime = doc.mime_type or ""

        # Only handle PDFs and text files
        supported = mime in (
            "application/pdf",
            "text/plain",
            "text/html",
            "text/csv",
        ) or file_name.endswith((".pdf", ".txt", ".html", ".csv", ".md"))

        if not supported:
            await update.message.reply_text(
                f"Ich kann leider '{file_name}' nicht lesen. "
                "Schick mir PDFs, TXT, HTML oder CSV Dateien."
            )
            return

        await update.message.chat.send_action("typing")
        await update.message.reply_text(f"Lese '{file_name}'...")

        try:
            tg_file = await doc.get_file()
            file_bytes = await tg_file.download_as_bytearray()

            # Extract text from the file
            if mime == "application/pdf" or file_name.endswith(".pdf"):
                text_content = self._extract_pdf_text(bytes(file_bytes))
            else:
                text_content = bytes(file_bytes).decode("utf-8", errors="replace")

            # Cap at 10000 chars for the prompt
            if len(text_content) > 10000:
                text_content = text_content[:10000] + "\n\n[... gekürzt, Dokument zu lang]"

            # Build prompt with optional user caption
            caption = update.message.caption or ""
            if caption:
                prompt = f"Dokument '{file_name}':\n\n{text_content}\n\nAuftrag: {caption}"
            else:
                prompt = (
                    f"Dokument '{file_name}':\n\n{text_content}\n\n"
                    "Fasse das Dokument zusammen und extrahiere die wichtigsten Punkte."
                )

            response = await self.brain.process(prompt, user_id)
        except Exception as e:
            logger.error(f"Document error: {e}")
            response = (
                f"Ich konnte '{file_name}' leider nicht verarbeiten. "
                "Versuch's nochmal oder schick es als Text."
            )

        # Split long responses (Telegram max 4096 chars)
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)

        if not is_authorized(user_id, self.allowed_ids):
            await update.message.reply_text(
                "Hallo! Ich bin leider nur für bestimmte Personen verfügbar."
            )
            return

        if not self.rate_limiter.check(user_id):
            await update.message.reply_text(
                "Du sendest gerade sehr viele Nachrichten. Warte kurz."
            )
            return

        voice = update.message.voice or update.message.audio
        if not voice:
            return

        # Max 15 minutes
        if voice.duration and voice.duration > 900:
            await update.message.reply_text(
                "Die Sprachmemo ist zu lang (max 15 Minuten). "
                "Schick mir bitte eine kürzere."
            )
            return

        await update.message.chat.send_action("typing")
        await update.message.reply_text("Höre zu...")

        try:
            import openai

            tg_file = await voice.get_file()
            file_bytes = await tg_file.download_as_bytearray()

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp.write(bytes(file_bytes))
                tmp_path = tmp.name

            try:
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                with open(tmp_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="de",
                    )
                text = transcript.text.strip()
            finally:
                os.unlink(tmp_path)

            if not text:
                await update.message.reply_text(
                    "Ich konnte nichts verstehen. Versuch's nochmal."
                )
                return

            logger.info(f"Voice transcribed ({voice.duration}s): {text[:80]}...")

            response = await self.brain.process(text, user_id)
        except Exception as e:
            logger.error(f"Voice error: {e}")
            response = (
                "Ich konnte die Sprachmemo nicht verarbeiten. "
                "Versuch's nochmal oder schick mir einen Text."
            )

        # Handle special return types (e.g. file_send)
        if isinstance(response, dict) and response.get("type") == "send_file":
            try:
                await update.message.reply_document(
                    document=open(response["path"], "rb"),
                    filename=os.path.basename(response["path"]),
                )
            except Exception as e:
                logger.error(f"File send error: {e}")
                await update.message.reply_text(f"Konnte Datei nicht senden: {e}")
            return

        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes using PyPDF2."""
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages) if pages else "[PDF enthält keinen lesbaren Text]"
        except ImportError:
            return "[PDF-Reader nicht installiert — bitte als Text schicken]"
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return f"[PDF konnte nicht gelesen werden: {e}]"

    def run(self):
        self._app.add_handler(CommandHandler("start", self.handle_start))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        self._app.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_document)
        )
        self._app.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, self.handle_voice)
        )
        logger.info(f"{self.config.name} ist online")
        self._app.run_polling()
