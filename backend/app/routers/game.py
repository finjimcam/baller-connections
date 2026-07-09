import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..db import db
from ..graph import get_graph
from ..lazy_import import ensure_player_known
from ..models import (
    PuzzleResponse,
    SolutionResponse,
    ValidateRequest,
    ValidateResponse,
    player_card,
)
from ..puzzles import PuzzleUnavailable, free_game, get_daily, shared_stints

router = APIRouter()


class FreeGameRequest(BaseModel):
    difficulty: str = "medium"


def _player_row(conn: sqlite3.Connection, player_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown player {player_id}")
    return row


@router.get("/daily", response_model=PuzzleResponse)
async def daily(request: Request):
    graph = get_graph()
    tm = request.app.state.tm
    with db() as conn:
        try:
            puzzle_date, start_id, target_id, par = get_daily(conn, graph)
        except PuzzleUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        # Pull both endpoints' full transfer histories once (no-op when already
        # synced) so every later guess — including the winning link to the
        # target — resolves from the local DB alone.
        await ensure_player_known(conn, tm, graph, start_id)
        await ensure_player_known(conn, tm, graph, target_id)
        return PuzzleResponse(
            mode="daily",
            date=puzzle_date,
            par=par,
            start=player_card(_player_row(conn, start_id)),
            target=player_card(_player_row(conn, target_id)),
        )


@router.post("/free-game", response_model=PuzzleResponse)
async def new_free_game(body: FreeGameRequest, request: Request):
    graph = get_graph()
    tm = request.app.state.tm
    with db() as conn:
        try:
            start_id, target_id, par = free_game(conn, graph, body.difficulty)
        except PuzzleUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        await ensure_player_known(conn, tm, graph, start_id)
        await ensure_player_known(conn, tm, graph, target_id)
        return PuzzleResponse(
            mode="free",
            par=par,
            start=player_card(_player_row(conn, start_id)),
            target=player_card(_player_row(conn, target_id)),
        )


@router.post("/validate", response_model=ValidateResponse)
async def validate(body: ValidateRequest, request: Request):
    graph = get_graph()
    tm = request.app.state.tm
    with db() as conn:
        # Fast path: answer from the local DB when it already proves the link —
        # the TM scraper sits behind a 2.5s/request politeness gate, so touching
        # it on every guess is what made validation feel slow.
        to_row = conn.execute(
            "SELECT * FROM players WHERE id = ?", (body.to_id,)
        ).fetchone()
        links = shared_stints(conn, body.from_id, body.to_id) if to_row else []
        if not links:
            # No local link: pull both players' full transfer histories before
            # declaring them never-teammates. Covers the puzzle's start player
            # too, which never otherwise passes through as a to_id.
            await ensure_player_known(conn, tm, graph, body.from_id)
            to_row = await ensure_player_known(conn, tm, graph, body.to_id)
            if to_row is None:
                return ValidateResponse(connected=False, reason="player-unknown")
            links = shared_stints(conn, body.from_id, body.to_id)
        if not links:
            return ValidateResponse(
                connected=False, reason="not-teammates", player=player_card(to_row)
            )
        # A valid guess may itself complete the puzzle: check it against the
        # target (purely local — the target was fully synced at puzzle load).
        target_links = []
        if body.target_id and body.target_id != body.to_id:
            target_links = shared_stints(conn, body.to_id, body.target_id)
            # to_row got here via the fast path (a local link already proved it
            # connects to from_id), so it may never have had its own full
            # transfer history pulled — meaning it can link backward into the
            # chain while still missing stints needed to link forward to the
            # target. Force the one-time sync and recheck before ruling it out.
            if not target_links and not to_row["transfers_synced_at"]:
                to_row = await ensure_player_known(conn, tm, graph, body.to_id)
                target_links = shared_stints(conn, body.to_id, body.target_id)
        return ValidateResponse(
            connected=True,
            links=links,
            player=player_card(to_row),
            target_links=target_links,
        )


@router.get("/solution", response_model=SolutionResponse)
async def solution(start_id: str, target_id: str):
    graph = get_graph()
    path = graph.shortest_path(start_id, target_id)
    if path is None:
        raise HTTPException(status_code=404, detail="no route between these players")
    with db() as conn:
        route = [player_card(_player_row(conn, pid)) for pid in path]
        connections = [shared_stints(conn, a, b) for a, b in zip(path, path[1:])]
    return SolutionResponse(length=len(path) - 1, route=route, connections=connections)
