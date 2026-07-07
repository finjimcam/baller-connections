"""In-process daily job: refresh current-season squads, rebuild the graph,
then pre-generate and pre-warm today's puzzle. Runs inside the API process so
the graph swap is atomic with no cross-process signaling."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from . import graph as graph_module
from . import images
from .config import settings
from .db import connect, db
from .ingest.pipeline import IngestLocked, refresh
from .puzzles import PuzzleUnavailable, get_daily

log = logging.getLogger(__name__)


async def daily_job(app: FastAPI) -> None:
    log.info("daily job starting")
    try:
        await refresh(app.state.tm, settings.ingest_config)
    except IngestLocked as exc:
        log.warning("daily refresh skipped: %s", exc)
    except Exception:
        log.exception("daily refresh failed; continuing with existing data")

    def _rebuild():
        conn = connect()
        try:
            return graph_module.Graph.build(conn)
        finally:
            conn.close()

    graph_module.set_graph(await asyncio.to_thread(_rebuild))

    try:
        with db() as conn:
            _, start_id, target_id, par = get_daily(conn, graph_module.get_graph())
        for player_id in (start_id, target_id):
            await images.player_image(app.state.tm, player_id)
        log.info("daily job done: puzzle %s -> %s (par %d) pre-warmed", start_id, target_id, par)
    except PuzzleUnavailable as exc:
        log.warning("daily puzzle not generated: %s", exc)


def start_scheduler(app: FastAPI) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=settings.daily_refresh_hour_utc, minute=0),
        args=[app],
        id="daily-refresh",
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler
