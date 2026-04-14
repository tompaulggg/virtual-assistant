import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.jobs: list[str] = []

    def add_cron(self, name: str, func, **cron_kwargs):
        job = self.scheduler.add_job(func, "cron", id=name, misfire_grace_time=300, **cron_kwargs)
        self.jobs.append(name)
        logger.info(f"Scheduled cron job: {name}")
        return job

    def add_interval(self, name: str, func, **interval_kwargs):
        job = self.scheduler.add_job(func, "interval", id=name, **interval_kwargs)
        self.jobs.append(name)
        logger.info(f"Scheduled interval job: {name}")
        return job

    def start(self):
        self.scheduler.start()
        logger.info(f"Scheduler started with {len(self.jobs)} jobs")

    def stop(self):
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
