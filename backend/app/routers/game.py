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
async def daily():
    graph = get_graph()
    with db() as conn:
        try:
            puzzle_date, start_id, target_id, par = get_daily(conn, graph)
        except PuzzleUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        return PuzzleResponse(
            mode="daily",
            date=puzzle_date,
            par=par,
            start=player_card(_player_row(conn, start_id)),
            target=player_card(_player_row(conn, target_id)),
        )


@router.post("/free-game", response_model=PuzzleResponse)
async def new_free_game(body: FreeGameRequest):
    graph = get_graph()
    with db() as conn:
        try:
            start_id, target_id, par = free_game(conn, graph, body.difficulty)
        except PuzzleUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
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
        to_row = await ensure_player_known(conn, tm, graph, body.to_id)
        if to_row is None:
            return ValidateResponse(connected=False, reason="player-unknown")
        links = shared_stints(conn, body.from_id, body.to_id)
        if not links:
            return ValidateResponse(
                connected=False, reason="not-teammates", player=player_card(to_row)
            )
        return ValidateResponse(connected=True, links=links, player=player_card(to_row))


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
