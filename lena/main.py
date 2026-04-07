"""Lena — Executive Assistant for Esther. Entry point."""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Ensure event loop exists (needed for Python 3.12+ / APScheduler)
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Add project root to path so core/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("lena")

from core import AssistantConfig, Brain, Bot, Scheduler
from lena.actions import ghostwriter, todos, reminders, knowledge, briefing


def register_actions(brain: Brain):
    """Register all Lena actions with the brain."""
    modules = [ghostwriter, todos, reminders, knowledge, briefing]

    for module in modules:
        for action_def in module.register():
            brain.register_action(
                name=action_def["name"],
                description=action_def["description"],
                parameters=action_def["parameters"],
                handler=action_def["handler"],
            )

    # Inject ghostwriter instructions as a prompt extension (not an action)
    brain.add_prompt_extension(ghostwriter.GHOSTWRITER_INSTRUCTIONS)

    logger.info(f"Registered {len(brain.actions)} actions")


def setup_scheduler(scheduler: Scheduler, bot_instance):
    """Register Lena's scheduled jobs."""
    from lena.actions.reminders import ReminderStore
    from lena.actions.todos import TodoStore
    from lena.actions.briefing import build_morning_briefing

    reminder_store = ReminderStore()
    todo_store = TodoStore()
    allowed_ids = os.getenv("ALLOWED_USER_IDS", "").split(",")

    async def check_reminders():
        due = await reminder_store.get_due()
        for r in due:
            try:
                await bot_instance.bot.send_message(
                    chat_id=r["user_id"],
                    text=f"Erinnerung: {r['text']}",
                )
                await reminder_store.mark_sent(r["id"])
            except Exception as e:
                logger.error(f"Failed to send reminder: {e}")

    async def morning_briefing():
        for user_id in allowed_ids:
            if not user_id.strip():
                continue
            try:
                text = await build_morning_briefing(
                    user_id.strip(), todo_store, reminder_store
                )
                await bot_instance.bot.send_message(
                    chat_id=user_id.strip(),
                    text=text,
                )
            except Exception as e:
                logger.error(f"Failed to send briefing: {e}")

    scheduler.add_interval("reminder_check", check_reminders, seconds=60)
    scheduler.add_cron("morning_briefing", morning_briefing, hour=7, minute=30)
    logger.info("Scheduler jobs registered")


def main():
    config_path = str(Path(__file__).parent / "config.yaml")
    config = AssistantConfig.from_yaml(config_path)

    brain = Brain(config)
    register_actions(brain)

    bot = Bot(brain, config)
    scheduler = Scheduler()

    # Wire up scheduler jobs before starting the bot
    setup_scheduler(scheduler, bot.get_application())

    # Start scheduler inside the bot's event loop via post_init
    async def on_startup(application):
        scheduler.start()
        logger.info(f"{config.name} ist online")

    bot.get_application().post_init = on_startup

    bot.run()


if __name__ == "__main__":
    main()
