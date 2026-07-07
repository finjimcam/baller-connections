"""Ingest CLI. Run inside the backend container, e.g.:

  docker compose exec -d backend uv run python -m app.ingest backfill
  docker compose exec backend uv run python -m app.ingest refresh
  docker compose exec -d backend uv run python -m app.ingest enrich-photos --top 2000

Long runs log to stdout and /data/ingest.log; tail with:
  docker compose exec backend tail -f /data/ingest.log
"""

import argparse
import asyncio
import logging
from pathlib import Path

from ..config import settings
from ..db import init_db
from ..tm_client import TMClient
from . import pipeline


def _setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        log_path = Path(settings.database_path).parent / "ingest.log"
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )


async def _run(args: argparse.Namespace) -> None:
    tm = TMClient()
    try:
        if args.command == "backfill":
            await pipeline.backfill(tm, args.config)
        elif args.command == "refresh":
            await pipeline.refresh(tm, args.config)
        elif args.command == "enrich-photos":
            await pipeline.enrich_photos(tm, args.top)
    finally:
        await tm.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    p_backfill = sub.add_parser("backfill", help="pull every configured club-season not yet done")
    p_backfill.add_argument("--config", default=settings.ingest_config)

    p_refresh = sub.add_parser("refresh", help="re-pull only the current season's squads")
    p_refresh.add_argument("--config", default=settings.ingest_config)

    p_photos = sub.add_parser("enrich-photos", help="pre-fetch portraits for the fame pool")
    p_photos.add_argument("--top", type=int, default=2000)

    args = parser.parse_args()
    _setup_logging()
    init_db()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
