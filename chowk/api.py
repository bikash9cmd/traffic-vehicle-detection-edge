"""HTTP API (FastAPI, local). The same routes run on Lambda in chowk/aws/handlers.py."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from chowk.status import approach_status, flow_window, junctions
from chowk.store import FlowStore, LocalStore


def create_app(store: FlowStore | None = None) -> FastAPI:
    store = store or LocalStore()
    app = FastAPI(title="Chowk", description="15-minute PCU flows at Kathmandu junctions")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/junctions")
    def list_junctions() -> dict:
        return {k: v["name"] for k, v in junctions().items()} | {"replay": "Replayed recording sessions"}

    def approaches_of(junction_id: str) -> dict:
        if junction_id == "replay":  # recorded sessions from `make replay` and the demo
            return {"recorded_clips": None}
        j = junctions().get(junction_id)
        if j is None:
            raise HTTPException(404, f"unknown junction {junction_id}")
        return j["approaches"]

    @app.get("/junctions/{junction_id}/now")
    def now(junction_id: str) -> dict:
        approaches = approaches_of(junction_id)
        return {"junction": junction_id,
                "approaches": [approach_status(store, junction_id, a, g) for a, g in approaches.items()]}

    @app.get("/junctions/{junction_id}/{approach_id}/flows")
    def flows(junction_id: str, approach_id: str, since: str | None = None, hours: int = 24) -> dict:
        if approach_id not in approaches_of(junction_id):
            raise HTTPException(404, f"unknown approach {approach_id}")
        if not 1 <= hours <= 24 * 31:
            raise HTTPException(400, "hours must be between 1 and 744")
        # No `since`: every stored interval, which is what the replay sessions (2016 recordings) need.
        start, until = ("0000", "9999")
        if since:
            try:
                start, until = flow_window(since, hours)
            except ValueError as e:
                raise HTTPException(400, str(e)) from None
        return {"junction": junction_id, "approach": approach_id,
                "flows": store.query(junction_id, approach_id, start, until)}

    return app
