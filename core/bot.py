import os
import time
import logging
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
        self.allowed_ids = os.getenv("ALLOWED_USER_IDS", "").split(",")
        self.rate_limiter = RateLimiter(max_per_minute=20)
        self._app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()

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
            f"Hallo! Ich bin {self.config.name}, deine persönliche Assistentin.\n\n"
            f"Du kannst mir einfach schreiben was du brauchst, zum Beispiel:\n"
            f"• 'Schreib eine E-Mail an Herrn Müller'\n"
            f"• 'Erinner mich morgen früh ans Meeting'\n"
            f"• 'Was steht heute an?'\n\n"
            f"Ich bin immer da!"
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

        await update.message.reply_text(response)

    def run(self):
        self._app.add_handler(CommandHandler("start", self.handle_start))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        logger.info(f"{self.config.name} ist online")
        self._app.run_polling()
