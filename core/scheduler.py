from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, List

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScheduledJob:
    name: str
    interval_seconds: int
    factory: Callable[[], Awaitable[None]]


class Scheduler:
    """Minimal async scheduler that repeatedly runs registered coroutines."""

    def __init__(self) -> None:
        self._jobs: List[ScheduledJob] = []

    def register(self, name: str, factory: Callable[[], Awaitable[None]], interval_seconds: int) -> None:
        self._jobs.append(ScheduledJob(name=name, factory=factory, interval_seconds=interval_seconds))
        logger.info("Registered scheduled job %s (%ss interval)", name, interval_seconds)

    async def start(self) -> None:
        if not self._jobs:
            logger.warning("No scheduled jobs registered; scheduler idle")
            return
        await asyncio.gather(*(self._run(job) for job in self._jobs))

    async def _run(self, job: ScheduledJob) -> None:
        logger.info("Starting job %s", job.name)
        while True:
            start = time.time()
            try:
                await job.factory()
            except Exception as exc:  # pragma: no cover - defensive log
                logger.exception("Job %s failed: %s", job.name, exc)
            elapsed = time.time() - start
            wait_for = max(job.interval_seconds - elapsed, 0)
            await asyncio.sleep(wait_for)
