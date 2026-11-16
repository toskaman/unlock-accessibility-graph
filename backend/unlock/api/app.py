"""FastAPI application. Binds to localhost by default; no arbitrary Cypher endpoint.

Run:  python -m unlock serve   (see backend/unlock/__main__.py)
"""
from __future__ import annotations

import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .. import ALGORITHM_VERSION, __version__
from ..config import ROOT, STORE_PATH
from ..db import GraphStore
from ..engine import graph as G
from ..engine.service import InvalidScenario, NotFound, UnlockService
from . import explain as X

_ID = re.compile(r"^[A-Za-z0-9:._|\-]{1,200}$")


def _check_id(v: str, what: str = "id") -> str:
    if not _ID.fullmatch(v or ""):
        raise HTTPException(422, f"invalid {what}")
    return v


class ScenarioIn(BaseModel):
    name: str = Field("Simulated outage", max_length=120)
    overrides: dict[str, str] = Field(..., description="lift id -> AVAILABLE | UNAVAILABLE | UNKNOWN")
    kind: str = Field("SIMULATED_OUTAGE", pattern=r"^(SIMULATED_OUTAGE|SIMULATED_RESTORATION|WHAT_IF)$")

    @field_validator("overrides")
    @classmethod
    def _ids(cls, v: dict[str, str]) -> dict[str, str]:
        for k in v:
            if not _ID.fullmatch(k):
                raise ValueError("invalid lift id")
        return v


class OutageIn(BaseModel):
    lift_ids: list[str] = Field(..., min_length=1, max_length=20)


def create_app(store_path: Path | str = STORE_PATH) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        t = time.perf_counter()
        db = GraphStore(store_path)
        app.state.db = db
        try:
            app.state.svc = UnlockService(db)
        except Exception:
            db.close()  # release the single-writer lease before failing
            raise
        app.state.startup_seconds = round(time.perf_counter() - t, 3)
        try:
            yield
        finally:
            db.close()

    app = FastAPI(title="UNLOCK — The Accessibility Impact Graph", version=__version__, lifespan=lifespan)
    origins = os.environ.get("UNLOCK_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])

    @app.exception_handler(NotFound)
    async def _nf(_: Request, e: NotFound):
        return JSONResponse({"error": "not_found", "detail": str(e)}, status_code=404)

    @app.exception_handler(InvalidScenario)
    async def _inv(_: Request, e: InvalidScenario):
        return JSONResponse({"error": "invalid_scenario", "detail": str(e)}, status_code=422)

    def svc(req: Request) -> UnlockService:
        return req.app.state.svc

    @app.get("/api/health")
    def health(req: Request) -> dict[str, Any]:
        s = svc(req)
        return {"ok": True, "version": __version__, "algorithm_version": ALGORITHM_VERSION,
                "store": str(s.db.path), "startup_seconds": req.app.state.startup_seconds,
                "status_snapshot": s.freshness()}

    @app.get("/api/network/summary")
    def summary(req: Request):
        return svc(req).summary()

    @app.get("/api/network/stations")
    def stations(req: Request):
        return svc(req).station_list()

    @app.get("/api/network/stations/{station_id}")
    def station(req: Request, station_id: str, scenario_id: str | None = None, candidate_lift: str | None = None):
        _check_id(station_id); scenario_id and _check_id(scenario_id); candidate_lift and _check_id(candidate_lift)
        return svc(req).station_graph(station_id, scenario_id, candidate_lift)

    @app.get("/api/network/lifts/{lift_id}")
    def lift(req: Request, lift_id: str, scenario_id: str | None = None):
        _check_id(lift_id); scenario_id and _check_id(scenario_id)
        return svc(req).lift_detail(lift_id, scenario_id)

    @app.get("/api/scenarios")
    def scenarios(req: Request):
        return svc(req).list_scenarios()

    @app.post("/api/scenarios", status_code=201)
    def create(req: Request, body: ScenarioIn):
        return svc(req).create_scenario(body.name, body.overrides, body.kind)

    @app.get("/api/scenarios/{scenario_id}")
    def get(req: Request, scenario_id: str):
        return svc(req).get_scenario(_check_id(scenario_id))

    @app.delete("/api/scenarios/{scenario_id}", status_code=204)
    def delete(req: Request, scenario_id: str):
        svc(req).delete_scenario(_check_id(scenario_id))

    @app.post("/api/scenarios/simulate-outage", status_code=201)
    def simulate(req: Request, body: OutageIn):
        s = svc(req)
        for l in body.lift_ids:
            _check_id(l)
        names = ", ".join((s.lifts[l].name or l) if l in s.lifts else l for l in body.lift_ids)
        sc = s.create_scenario(f"Simulated outage: {names}"[:120], {l: "UNAVAILABLE" for l in body.lift_ids})
        return {"scenario": sc, "analysis": s.analyze(sc["id"])}

    @app.get("/api/scenarios/{scenario_id}/analysis")
    def analysis(req: Request, scenario_id: str):
        return svc(req).analyze(_check_id(scenario_id))

    @app.post("/api/scenarios/{scenario_id}/rank-interventions")
    def rank(req: Request, scenario_id: str, limit: int = Query(25, ge=1, le=200)):
        return svc(req).rank(_check_id(scenario_id), limit)

    @app.get("/api/baseline/rank-interventions")
    def rank_baseline(req: Request, limit: int = Query(25, ge=1, le=200)):
        return svc(req).rank(None, limit)

    @app.get("/api/scenarios/{scenario_id}/plan")
    def plan(req: Request, scenario_id: str, budget: int = Query(2, ge=1, le=5)):
        return svc(req).plan(_check_id(scenario_id), budget)

    @app.get("/api/baseline/plan")
    def plan_baseline(req: Request, budget: int = Query(2, ge=1, le=5)):
        return svc(req).plan(None, budget)

    @app.get("/api/pairs/explain")
    def explain(req: Request, pair_id: str, scenario_id: str | None = None, candidate_lift: str | None = None):
        _check_id(pair_id, "pair id"); scenario_id and _check_id(scenario_id); candidate_lift and _check_id(candidate_lift)
        data = svc(req).explain_pair(pair_id, scenario_id, candidate_lift)
        data["narrative"] = X.explain_pair(data)
        return data

    @app.get("/api/scenarios/{scenario_id}/with-candidate")
    def with_candidate(req: Request, scenario_id: str, candidate_lift: str):
        return svc(req).counts_with(_check_id(scenario_id), _check_id(candidate_lift))

    @app.post("/api/scenarios/{scenario_id}/export")
    def export(req: Request, scenario_id: str):
        return svc(req).export(_check_id(scenario_id))

    @app.get("/api/analyst/explain-candidate")
    def explain_candidate(req: Request, scenario_id: str, lift_id: str):
        _check_id(scenario_id); _check_id(lift_id)
        s = svc(req)
        ranking = s.rank(scenario_id, limit=200)
        return X.explain_candidate(ranking, lift_id, s.analyze(scenario_id))

    @app.get("/api/debug/queries")
    def queries(req: Request, limit: int = Query(30, ge=1, le=200)):
        """Recent Cypher statements actually executed by the store (for inspection)."""
        return {"store": str(svc(req).db.path), "queries": svc(req).db.recent(limit),
                "catalog": {"routes": G.Q_ROUTES.strip(), "route_path": G.Q_ROUTE_PATH.strip(),
                            "lift_evidence": G.Q_LIFT_EVIDENCE.strip(), "lift_states": G.Q_LIFT_STATES.strip(),
                            "endpoint_assertions": G.Q_ENDPOINT_ASSERTIONS.strip()}}

    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = (dist / path).resolve()
            if path and f.is_file() and dist.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(dist / "index.html")

    return app
