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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .. import ALGORITHM_VERSION, __version__
from ..config import ROOT, STORE_PATH
from ..db import GraphStore
from ..engine import graph as G
from ..engine.service import InvalidScenario, NotFound, UnlockService
from ..network.service import NetworkService
from . import explain as X

_ID = re.compile(r"^[A-Za-z0-9:._|@\-]{1,200}$")


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


class IncidentIn(BaseModel):
    text: str = Field(..., min_length=3, max_length=1000)


class WhatIfIn(BaseModel):
    overrides: dict[str, str] = Field(..., description="lift id -> AVAILABLE | UNAVAILABLE | UNKNOWN")

    @field_validator("overrides")
    @classmethod
    def _ids(cls, v: dict[str, str]) -> dict[str, str]:
        for k in v:
            if not _ID.fullmatch(k):
                raise ValueError("invalid lift id")
        return v


class LegIn(BaseModel):
    board: str = Field(..., max_length=120, pattern=r"^[A-Za-z0-9:_.@\-]+$")
    alight: str = Field(..., max_length=120, pattern=r"^[A-Za-z0-9:_.@\-]+$")
    line: str = Field(..., max_length=120, pattern=r"^[A-Za-z0-9:_.@\-]+$")


class TripIn(BaseModel):
    label: str | None = Field(None, max_length=60)
    from_: str = Field(..., alias="from", max_length=120)
    to: str = Field(..., max_length=120)
    usual: list[LegIn] | None = Field(None, max_length=12)
    last_status: str | None = Field(None, max_length=30)


class TripsIn(BaseModel):
    trips: list[TripIn] = Field(..., min_length=1, max_length=20)


class OutageIn(BaseModel):
    lift_ids: list[str] = Field(..., min_length=1, max_length=20)


def _default_regions(store_path: Path) -> dict[str, Path]:
    """Other regions built by `python -m unlock build-region <code>` (database/regions/<code>.rl), served read-only."""
    if os.environ.get("UNLOCK_REGIONS", "1") == "0" or Path(store_path).resolve() != Path(STORE_PATH).resolve():
        return {}
    d = Path(STORE_PATH).parent / "regions"
    return {p.stem: p for p in sorted(d.glob("*.rl"))} if d.exists() else {}


def create_app(store_path: Path | str = STORE_PATH, regions: dict[str, Path] | None = None) -> FastAPI:
    regions = _default_regions(Path(store_path)) if regions is None else regions

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        t = time.perf_counter()
        db = GraphStore(store_path)
        app.state.db = db
        extra_dbs = []
        try:
            app.state.svc = UnlockService(db)
            app.state.net = NetworkService(db, app.state.svc)
            app.state.net.warm()  # region views + ranking (~1.5 s, pure Python)
            app.state.regions = {app.state.net.region["code"] if app.state.net.ready else "idf": app.state.net}
            for code, path in regions.items():
                rdb = GraphStore(path, read_only=True)
                extra_dbs.append(rdb)
                rn = NetworkService(rdb, UnlockService(rdb))
                if rn.ready:
                    rn.warm()
                    rn.region = {**rn.region, "code": code}
                    app.state.regions[code] = rn
        except Exception:
            for x in [db, *extra_dbs]:
                x.close()  # release the single-writer lease before failing
            raise
        app.state.startup_seconds = round(time.perf_counter() - t, 3)
        try:
            yield
        finally:
            for x in [db, *extra_dbs]:
                x.close()

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

    @app.post("/api/incidents/resolve")
    def resolve_incident(req: Request, body: IncidentIn):
        """Free-text outage report -> lift in the graph (deterministic, graph-grounded)."""
        return svc(req).resolve_incident(body.text)

    @app.post("/api/what-if")
    def what_if(req: Request, body: WhatIfIn):
        """Transient analysis: nothing is written to the store."""
        return svc(req).what_if(body.overrides)

    @app.get("/api/network/critical-lifts")
    def critical(req: Request, limit: int = Query(20, ge=1, le=600)):
        return svc(req).critical_lifts(limit)

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

    # ------------------------------------------------------------ region (network mode)
    def net(req: Request) -> NetworkService:
        code = req.query_params.get("region")
        if code and code not in req.app.state.regions:
            raise HTTPException(404, f"unknown region {code[:20]!r}")
        n = req.app.state.regions[code] if code else req.app.state.net
        if not n.ready:
            raise HTTPException(404, "network layer not imported — run `python -m unlock build`")
        return n

    _VIEW = r"^(best|feed|published)$"

    @app.get("/api/regions")
    def regions_list(req: Request):
        return [{**n.region, "default": n is req.app.state.net} for n in req.app.state.regions.values() if n.ready]

    @app.get("/api/region/overview")
    def region_overview(req: Request):
        return net(req).overview()

    @app.get("/api/region/map")
    def region_map(req: Request, view: str = Query("best", pattern=_VIEW)):
        return net(req).map_layer(view)

    @app.get("/api/region/rank")
    def region_rank(req: Request, limit: int = Query(12, ge=1, le=100)):
        return net(req).rank(limit)

    @app.get("/api/region/stations")
    def region_stations(req: Request, q: str = Query(..., min_length=1, max_length=60)):
        return net(req).station_search(q)

    @app.get("/api/region/journey")
    def region_journey(req: Request, a: str = Query(..., alias="from"), b: str = Query(..., alias="to"),
                       view: str = Query("best", pattern=_VIEW)):
        n = net(req)
        try:
            return n.check_journey(_check_id(a), _check_id(b), view)
        except KeyError:
            raise HTTPException(404, "unknown station")

    @app.post("/api/region/trips/check")
    def region_trips(req: Request, body: TripsIn):
        """Rider alerts: status of each usual trip today (OK / DETOUR / AT_RISK / CUT / NO_STEP_FREE_ROUTE).
        Stateless: the client keeps its trips and sends back the last status it saw."""
        from ..network.alerts import check
        trips = [{"label": t.label, "from": t.from_, "to": t.to, "last_status": t.last_status,
                  **({"usual": [l.model_dump() for l in t.usual]} if t.usual else {})} for t in body.trips]
        try:
            return {"trips": check(net(req), trips)}
        except KeyError as e:
            raise HTTPException(422, f"unknown boarding point in usual route: {e}")

    @app.get("/api/region/bulletin")
    def region_bulletin(req: Request):
        from ..network import bulletin as B
        n = net(req)
        if "bulletin" not in n._cache:
            b = B.build(n)
            n._cache["bulletin"] = {**b, "markdown": B.to_markdown(b), "html": B.to_html(b)}
        return {k: v for k, v in n._cache["bulletin"].items() if k != "html"}

    @app.get("/api/region/bulletin.html", response_class=HTMLResponse)
    def region_bulletin_html(req: Request):
        region_bulletin(req)
        return HTMLResponse(net(req)._cache["bulletin"]["html"])

    @app.get("/api/region/reach")
    def region_reach(req: Request, a: str = Query(..., alias="from"), view: str = Query("best", pattern=_VIEW)):
        n = net(req)
        try:
            return n.reach(_check_id(a), view)
        except KeyError:
            raise HTTPException(404, "unknown station")

    @app.get("/api/region/stations/{station_id}/outages")
    def region_station_outages(req: Request, station_id: str, view: str = Query("best", pattern=_VIEW)):
        n = net(req)
        if _check_id(station_id) not in n.stations:
            raise HTTPException(404, "unknown station")
        return {"station": n._st(station_id), "outages": n.station_outages(station_id, view),
                "lifts": n.station_lifts(station_id), "lift_status_source": n.idfm_feed}

    @app.get("/api/region/outages/{outage_id}")
    def region_outage(req: Request, outage_id: str):
        n = net(req)
        if _check_id(outage_id) not in n.outages:
            raise HTTPException(404, "unknown outage")
        return n.outage_view(outage_id)

    @app.get("/api/region/reconciliation")
    def region_reconciliation(req: Request, limit: int = Query(50, ge=1, le=400)):
        n = net(req)
        rec = n.reconciliation()
        rows = []
        for r in rec["rows"][:limit]:
            o = n.outages[r["outage"]]
            rows.append({**r, "text": o["text"], "station": n.stations[o["station_id"]]["name"],
                         "lift_name": n.ss.lifts[r["lift"]].name if r.get("lift") in n.ss.lifts else None})
        missing = [{"lift": l, "name": n.ss.lifts[l].name, "station": n.ss.stations.get(n.ss.lifts[l].station_id, {}).get("name")}
                   for l in rec["missing"]]
        return {"counts": rec["counts"], "rows": rows, "missing_from_feed": missing, "feed": n.feed_info()}

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
            if path.startswith("api/") or path == "api":
                raise HTTPException(404, "unknown API route")
            f = (dist / path).resolve()
            if path and f.is_file() and dist.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(dist / "index.html")

    return app
