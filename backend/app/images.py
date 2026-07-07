"""Lazy caching image proxy for player portraits and club crests.

Browsers never touch the Transfermarkt CDN: the backend fetches each image at
most once (rate-limited), stores it in the /data volume forever, and serves it
with long-lived cache headers. A zero-byte file is the permanent "no image"
sentinel; transient failures return 204 without a sentinel so they retry later.
"""

import logging
import os
from pathlib import Path
from urllib.parse import quote

from fastapi.responses import FileResponse, Response

from .config import settings
from .db import db
from .tm_client import TMClient, TMError

log = logging.getLogger(__name__)

CREST_URL_PATTERN = "https://tmssl.akamaized.net/images/wappen/head/{club_id}.png"
CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}


def _cache_path(kind: str, item_id: str, ext: str) -> Path:
    safe_id = "".join(c for c in item_id if c.isalnum() or c in "-_")
    path = Path(settings.image_cache_dir) / kind / f"{safe_id}{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _serve(path: Path, media_type: str) -> Response:
    if path.stat().st_size == 0:
        return Response(status_code=204)
    return FileResponse(path, media_type=media_type, headers=CACHE_HEADERS)


def _store(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


async def player_image(tm: TMClient, player_id: str) -> Response:
    path = _cache_path("players", player_id, ".jpg")
    if path.exists():
        return _serve(path, "image/jpeg")

    with db() as conn:
        row = conn.execute(
            "SELECT image_url, profile_synced_at FROM players WHERE id = ?", (player_id,)
        ).fetchone()
        if row is None:
            return Response(status_code=404)
        image_url = row["image_url"]
        if not image_url and not row["profile_synced_at"]:
            # One-time profile fetch to learn the portrait URL.
            try:
                profile = await tm.get(f"/players/{quote(player_id)}/profile")
            except TMError:
                return Response(status_code=204)  # transient — retry on a later view
            image_url = profile.get("imageUrl")
            conn.execute(
                """UPDATE players SET image_url = ?, profile_synced_at = datetime('now')
                   WHERE id = ?""",
                (image_url, player_id),
            )

    if not image_url or "default" in image_url:
        path.touch()  # permanent: this player has no portrait
        return Response(status_code=204)

    data = await tm.get_image(image_url)
    if data is None:
        return Response(status_code=204)
    _store(path, data)
    with db() as conn:
        conn.execute(
            "UPDATE players SET image_cached_at = datetime('now') WHERE id = ?", (player_id,)
        )
    return _serve(path, "image/jpeg")


async def club_crest(tm: TMClient, club_id: str) -> Response:
    path = _cache_path("crests", club_id, ".png")
    if path.exists():
        return _serve(path, "image/png")

    with db() as conn:
        row = conn.execute("SELECT crest_url FROM clubs WHERE id = ?", (club_id,)).fetchone()
    if row is None:
        return Response(status_code=404)
    url = row["crest_url"] or CREST_URL_PATTERN.format(club_id=club_id)
    data = await tm.get_image(url)
    if data is None:
        return Response(status_code=204)
    _store(path, data)
    return _serve(path, "image/png")
