from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from .. import images
from ..db import db, normalize_name
from ..lazy_import import search_fallback
from ..models import PlayerCard, SearchResult, player_card

router = APIRouter()


def _latest_club(conn, player_id: str) -> str | None:
    row = conn.execute(
        """SELECT c.name FROM squad_memberships m JOIN clubs c ON c.id = m.club_id
           WHERE m.player_id = ? ORDER BY m.season_id DESC LIMIT 1""",
        (player_id,),
    ).fetchone()
    return row["name"] if row else None


def _result(conn, row) -> SearchResult:
    dob = row["date_of_birth"]
    birth_year = int(dob[:4]) if dob and len(dob) >= 4 and dob[:4].isdigit() else None
    return SearchResult(
        id=row["id"],
        name=row["name"],
        position=row["position"],
        nationality=row["nationality"],
        birth_year=birth_year,
        latest_club=_latest_club(conn, row["id"]),
    )


@router.get("/players/search", response_model=list[SearchResult])
async def search_players(
    request: Request,
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=8, ge=1, le=20),
):
    norm = normalize_name(q)
    with db() as conn:
        rows = conn.execute(
            """SELECT *, CASE WHEN normalized_name LIKE ? THEN 0 ELSE 1 END AS rank
               FROM players
               WHERE normalized_name LIKE ?
               ORDER BY rank, COALESCE(peak_market_value, 0) DESC, membership_count DESC
               LIMIT ?""",
            (norm + "%", "%" + norm + "%", limit),
        ).fetchall()
        if not rows:
            # Nothing local — fall back to a live transfermarkt search.
            rows = await search_fallback(conn, request.app.state.tm, q, limit)
        return [_result(conn, r) for r in rows]


@router.get("/players/{player_id}", response_model=PlayerCard)
async def player_detail(player_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown player {player_id}")
    return player_card(row)


@router.get("/players/{player_id}/image")
async def player_image(player_id: str, request: Request) -> Response:
    return await images.player_image(request.app.state.tm, player_id)


@router.get("/clubs/{club_id}/crest")
async def club_crest(club_id: str, request: Request) -> Response:
    return await images.club_crest(request.app.state.tm, club_id)
