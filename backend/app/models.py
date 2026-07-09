import sqlite3

from pydantic import BaseModel


class PlayerCard(BaseModel):
    id: str
    name: str
    position: str | None = None
    nationality: str | None = None
    birth_year: int | None = None
    image: str


class StintLink(BaseModel):
    """One shared club stint between two adjacent players in a chain."""

    club_id: str
    club_name: str
    is_national_team: bool = False
    crest: str
    seasons: list[str]  # display labels, consecutive seasons collapsed


class PuzzleResponse(BaseModel):
    mode: str
    date: str | None = None
    par: int  # shortest route length in hops
    start: PlayerCard
    target: PlayerCard


class SearchResult(BaseModel):
    id: str
    name: str
    position: str | None = None
    nationality: str | None = None
    birth_year: int | None = None
    latest_club: str | None = None


class ValidateRequest(BaseModel):
    from_id: str
    to_id: str
    # the puzzle's target player; when set, a successful guess is also checked
    # against it so the frontend can auto-complete the chain
    target_id: str | None = None


class ValidateResponse(BaseModel):
    connected: bool
    reason: str | None = None  # set when not connected: not-teammates | player-unknown
    links: list[StintLink] = []
    player: PlayerCard | None = None
    # shared stints between the guessed player and the puzzle target — non-empty
    # means this guess completes the chain
    target_links: list[StintLink] = []


class SolutionResponse(BaseModel):
    length: int  # hops
    route: list[PlayerCard]
    connections: list[list[StintLink]]  # one entry per hop


def player_card(row: sqlite3.Row) -> PlayerCard:
    dob = row["date_of_birth"]
    birth_year = None
    if dob and len(dob) >= 4 and dob[:4].isdigit():
        birth_year = int(dob[:4])
    return PlayerCard(
        id=row["id"],
        name=row["name"],
        position=row["position"],
        nationality=row["nationality"],
        birth_year=birth_year,
        image=f"/api/players/{row['id']}/image",
    )
