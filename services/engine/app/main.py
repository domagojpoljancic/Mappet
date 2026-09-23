"""FastAPI Route Engine for Mappet (mock pipeline).

Implements the client-facing contract from docs/ARCHITECTURE.md §6:
    POST /search            -> {job_id, status, results}
    GET  /search/{job_id}   -> same shape (for polling)
    GET  /route/{id}/gpx    -> GPX track download
    GET  /health            -> liveness probe

The heavy geospatial/CV work is stubbed by app.engine (see its docstring).
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engine import RouteResult, search

app = FastAPI(title="Mappet Route Engine", version="0.1.0")

# Frontend runs on a different origin in dev; allow it to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores (dev-only). Replace with real caches in Phase 1/2.
_JOBS: dict[str, list[dict]] = {}
_ROUTES: dict[str, RouteResult] = {}


class Origin(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class Preferences(BaseModel):
    avoid_busy_roads: bool = True
    prefer_quiet: bool = True


class SearchRequest(BaseModel):
    origin: Origin
    activity: Literal["run", "walk"] = "run"
    distance_km: float = Field(5.0, ge=2.0, le=100.0)
    tolerance: float = Field(0.15, ge=0.0, le=0.5)
    preferences: Preferences = Preferences()


class SearchResponse(BaseModel):
    job_id: str
    status: str
    results: list[dict]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "route-engine", "version": app.version}


@app.post("/search", response_model=SearchResponse)
def create_search(req: SearchRequest) -> SearchResponse:
    results = search(
        origin_lat=req.origin.lat,
        origin_lng=req.origin.lng,
        activity=req.activity,
        distance_km=req.distance_km,
        tolerance=req.tolerance,
        prefer_quiet=req.preferences.prefer_quiet,
        avoid_busy_roads=req.preferences.avoid_busy_roads,
    )
    for r in results:
        _ROUTES[r.route_id] = r

    job_id = uuid.uuid4().hex
    payload = [r.to_dict() for r in results]
    _JOBS[job_id] = payload
    status = "complete" if payload else "empty"
    return SearchResponse(job_id=job_id, status=status, results=payload)


@app.get("/search/{job_id}", response_model=SearchResponse)
def get_search(job_id: str) -> SearchResponse:
    if job_id not in _JOBS:
        raise HTTPException(status_code=404, detail="job not found")
    payload = _JOBS[job_id]
    status = "complete" if payload else "empty"
    return SearchResponse(job_id=job_id, status=status, results=payload)


@app.get("/route/{route_id}/gpx")
def route_gpx(route_id: str) -> Response:
    route = _ROUTES.get(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="route not found")
    gpx = _to_gpx(route)
    return Response(
        content=gpx,
        media_type="application/gpx+xml",
        headers={
            "Content-Disposition": f'attachment; filename="{route.label}-{route_id}.gpx"'
        },
    )


def _to_gpx(route: RouteResult) -> str:
    pts = "\n".join(
        f'      <trkpt lat="{lat}" lon="{lng}"></trkpt>' for lat, lng in route.polyline
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="Mappet" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"  <metadata><name>Mappet - {route.label}</name></metadata>\n"
        "  <trk>\n"
        f"    <name>{route.label} ({route.route_id})</name>\n"
        "    <trkseg>\n"
        f"{pts}\n"
        "    </trkseg>\n"
        "  </trk>\n"
        "</gpx>\n"
    )
