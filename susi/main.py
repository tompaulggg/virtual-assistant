"""Susi — Co-Founder Assistant for Thomas. Entry point."""

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

# Add project root to path so core/ and lena/ are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("susi")

from core import AssistantConfig, Brain, Bot, Scheduler
# Reuse shared actions from Lena
from lena.actions import ghostwriter, todos, reminders, knowledge, briefing
# Susi-specific actions
from susi.actions import projects, ideas, claudia_bridge, email_sync, calendar_sync
from susi.actions import event_poller, event_handlers, inline_buttons
from susi.actions.morning_briefing_v2 import build_combined_briefing


def register_actions(brain: Brain):
    """Register all Susi actions with the brain."""
    # Shared actions
    shared = [ghostwriter, todos, reminders, knowledge, briefing]
    # Susi-only actions
    susi_only = [projects, ideas, claudia_bridge, email_sync, calendar_sync]

    for module in shared + susi_only:
        for action_def in module.register():
            brain.register_action(
                name=action_def["name"],
                description=action_def["description"],
                parameters=action_def["parameters"],
                handler=action_def["handler"],
            )

    brain.add_prompt_extension(ghostwriter.GHOSTWRITER_INSTRUCTIONS)
    logger.info(f"Registered {len(brain.actions)} actions")

    # Register MC event handlers
    event_poller.register_handler("channel_analyzed", event_handlers.handle_channel_analyzed)
    event_poller.register_handler("aufbau_review_ready", event_handlers.handle_aufbau_review_ready)
    event_poller.register_handler("aufbau_started", event_handlers.handle_aufbau_started)
    logger.info("MC event handlers registered")


def setup_scheduler(scheduler: Scheduler, bot_instance):
    """Register Susi's scheduled jobs."""
    from lena.actions.reminders import ReminderStore
    from lena.actions.todos import TodoStore
    from lena.actions.briefing import build_morning_briefing

    reminder_store = ReminderStore()
    todo_store = TodoStore()
    allowed_ids = os.getenv("SUSI_ALLOWED_USER_IDS", "").split(",")

    _cost_alert_sent_today = None

    async def check_reminders():
        nonlocal _cost_alert_sent_today
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

        # Cost alert check (once per day)
        from datetime import date
        today = date.today().isoformat()
        if _cost_alert_sent_today != today:
            from susi.actions.cost_tracker import is_cost_alert
            should_alert, alert_msg = is_cost_alert()
            if should_alert:
                _cost_alert_sent_today = today
                for user_id in allowed_ids:
                    if not user_id.strip():
                        continue
                    try:
                        await bot_instance.bot.send_message(
                            chat_id=user_id.strip(),
                            text=alert_msg,
                        )
                    except Exception as e:
                        logger.error(f"Failed to send cost alert: {e}")

    async def morning_briefing():
        # Fetch MC briefing data once (ACKs the event)
        from susi.actions.morning_briefing_v2 import _fetch_briefing_event
        mc_data = await _fetch_briefing_event()

        for user_id in allowed_ids:
            if not user_id.strip():
                continue
            try:
                text = await build_combined_briefing(
                    user_id.strip(), todo_store, reminder_store,
                    mc_data=mc_data,
                )
                await bot_instance.bot.send_message(
                    chat_id=user_id.strip(),
                    text=text,
                )
            except Exception as e:
                logger.error(f"Failed to send briefing: {e}")

    from susi.actions.cost_tracker import get_daily_summary

    async def daily_cost_report():
        for user_id in allowed_ids:
            if not user_id.strip():
                continue
            try:
                text = get_daily_summary()
                await bot_instance.bot.send_message(
                    chat_id=user_id.strip(),
                    text=text,
                )
            except Exception as e:
                logger.error(f"Failed to send cost report: {e}")

    # Email sync — read, learn, and alert on important emails
    from core.email_reader import EmailReader
    from core.memory import Memory as SusiMemory
    email_reader = EmailReader()
    email_memory = SusiMemory(bot_name="susi")

    async def email_sync_job():
        for user_id in allowed_ids:
            if not user_id.strip():
                continue
            try:
                # Learn from new emails
                result = await email_reader.sync_and_learn(
                    user_id.strip(), email_memory, hours=1
                )
                if "0 Fakten" not in result and "Keine" not in result:
                    logger.info(f"Email sync: {result}")

                # Check for important emails and alert
                emails = email_reader.fetch_recent(hours=1, max_emails=10)
                if emails:
                    classified = email_reader.classify_importance(emails)
                    important = [e for e in classified if e.get("type") == "wichtig"]
                    if important:
                        lines = ["📬 **Wichtige E-Mail(s) eingegangen:**\n"]
                        for e in important:
                            sender = e["from"].split("<")[0].strip().strip('"')
                            lines.append(f"• **{sender}**: {e['subject']}")
                            if e.get("reason"):
                                lines.append(f"  → {e['reason']}")
                        try:
                            await bot_instance.bot.send_message(
                                chat_id=user_id.strip(),
                                text="\n".join(lines),
                            )
                        except Exception as e2:
                            logger.error(f"Failed to send email alert: {e2}")
            except Exception as e:
                logger.error(f"Email sync failed: {e}")

    scheduler.add_interval("reminder_check", check_reminders, seconds=60)
    scheduler.add_interval("email_sync", email_sync_job, minutes=30)
    scheduler.add_cron("morning_briefing", morning_briefing, hour=8, minute=0)
    scheduler.add_cron("daily_cost_report", daily_cost_report, hour=22, minute=0)

    # Event poller — check MC for new events every 10 seconds
    async def poll_mc_events():
        await event_poller.poll_and_dispatch(bot_instance.bot, allowed_ids)

    scheduler.add_interval("mc_event_poller", poll_mc_events, seconds=10)
    logger.info("Scheduler jobs registered")


def main():
    config_path = str(Path(__file__).parent / "config.yaml")
    config = AssistantConfig.from_yaml(config_path)

    brain = Brain(config)
    register_actions(brain)

    bot = Bot(brain, config)
    scheduler = Scheduler()

    setup_scheduler(scheduler, bot.get_application())

    async def on_startup(application):
        scheduler.start()
        # Give claudia_bridge access to the telegram bot for async result delivery
        claudia_bridge.set_telegram_bot(application.bot)
        logger.info(f"{config.name} ist online")

    bot.get_application().post_init = on_startup

    # Add inline button callback handler and revision reply handler
    from telegram.ext import CallbackQueryHandler, MessageHandler, filters
    app = bot.get_application()
    app.add_handler(CallbackQueryHandler(inline_buttons.handle_callback))
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.REPLY & ~filters.COMMAND,
            inline_buttons.handle_revision_reply,
        ),
        group=0,
    )

    bot.run()


if __name__ == "__main__":
    main()
