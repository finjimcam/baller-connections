from __future__ import annotations

import logging
import sqlite3
import time
from collections import defaultdict
from typing import Iterable

log = logging.getLogger(__name__)


class Graph:
    """In-memory teammate graph. Nodes are player ids; an edge means the two
    players shared a club squad in some season."""

    def __init__(self, adj: dict[str, set[str]]):
        self.adj = adj

    @classmethod
    def build(cls, conn: sqlite3.Connection) -> Graph:
        started = time.monotonic()
        groups: dict[tuple[str, str], list[str]] = defaultdict(list)
        for club_id, season_id, player_id in conn.execute(
            "SELECT club_id, season_id, player_id FROM squad_memberships"
        ):
            groups[(club_id, season_id)].append(player_id)
        adj: dict[str, set[str]] = defaultdict(set)
        for members in groups.values():
            for i, a in enumerate(members):
                for b in members[i + 1 :]:
                    adj[a].add(b)
                    adj[b].add(a)
        graph = cls(dict(adj))
        log.info(
            "graph built: %d players, %d edges in %.1fs",
            len(graph.adj),
            graph.edge_count(),
            time.monotonic() - started,
        )
        return graph

    def edge_count(self) -> int:
        return sum(len(s) for s in self.adj.values()) // 2

    def neighbors(self, player_id: str) -> set[str]:
        return self.adj.get(player_id, set())

    def add_player(self, player_id: str, teammates: Iterable[str]) -> None:
        """Incrementally patch the graph after a lazy player import."""
        own = self.adj.setdefault(player_id, set())
        for t in teammates:
            if t == player_id:
                continue
            own.add(t)
            self.adj.setdefault(t, set()).add(player_id)

    def distances_from(self, start: str, max_depth: int) -> dict[str, int]:
        dist = {start: 0}
        frontier = [start]
        for depth in range(1, max_depth + 1):
            nxt: list[str] = []
            for node in frontier:
                for nb in self.adj.get(node, ()):
                    if nb not in dist:
                        dist[nb] = depth
                        nxt.append(nb)
            if not nxt:
                break
            frontier = nxt
        return dist

    def shortest_path(self, start: str, target: str) -> list[str] | None:
        """BFS shortest path as a list of player ids, endpoints included."""
        if start == target:
            return [start]
        if start not in self.adj or target not in self.adj:
            return None
        parents: dict[str, str | None] = {start: None}
        frontier = [start]
        while frontier:
            nxt: list[str] = []
            for node in frontier:
                for nb in self.adj.get(node, ()):
                    if nb in parents:
                        continue
                    parents[nb] = node
                    if nb == target:
                        path = [nb]
                        while parents[path[-1]] is not None:
                            path.append(parents[path[-1]])
                        path.reverse()
                        return path
                    nxt.append(nb)
            frontier = nxt
        return None


_graph: Graph | None = None


def get_graph() -> Graph:
    if _graph is None:
        raise RuntimeError("graph not built yet")
    return _graph


def set_graph(graph: Graph) -> None:
    global _graph
    _graph = graph
