import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import graph as graph_module
from .db import connect, init_db
from .routers import game, players
from .scheduler import start_scheduler
from .tm_client import TMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    def _build():
        conn = connect()
        try:
            return graph_module.Graph.build(conn)
        finally:
            conn.close()

    graph_module.set_graph(await asyncio.to_thread(_build))
    app.state.tm = TMClient()
    scheduler = start_scheduler(app)
    yield
    scheduler.shutdown(wait=False)
    await app.state.tm.close()


app = FastAPI(title="Baller Connections API", lifespan=lifespan)
app.include_router(game.router, prefix="/api")
app.include_router(players.router, prefix="/api")


@app.get("/api/health")
def health():
    conn = connect()
    try:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("players", "clubs", "squad_memberships")
        }
    finally:
        conn.close()
    try:
        g = graph_module.get_graph()
        graph_stats = {"graph_players": len(g.adj), "graph_edges": g.edge_count()}
    except RuntimeError:
        graph_stats = {"graph_players": 0, "graph_edges": 0}
    return {"status": "ok", **counts, **graph_stats}
