import csv
import json
import math
import os

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models import IngestRun, RouteSegment, RouteShape, ServiceAlert, Station, VehicleSnapshot

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# shape_id -> (direction_id, headsign), built once on first use
_shape_dir_cache: dict[str, tuple[int, str]] | None = None


def _shape_directions() -> dict[str, tuple[int, str]]:
    global _shape_dir_cache
    if _shape_dir_cache is not None:
        return _shape_dir_cache
    result: dict[str, tuple[int, str]] = {}
    with open(os.path.join(_DATA_DIR, "trips.txt"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sid = row.get("shape_id", "").strip()
            if sid and sid not in result:
                try:
                    did = int(row.get("direction_id", 0))
                except ValueError:
                    did = 0
                result[sid] = (did, row.get("trip_headsign", "").strip())
    _shape_dir_cache = result
    return result


def _project_onto_polyline(lat: float, lon: float, points: list) -> float:
    """Return cumulative arc-length parameter [0..1] of the nearest point
    on the polyline to (lat, lon), using a flat-earth approximation at NYC.
    """
    SLAT = 111_000.0
    SLON = 111_000.0 * math.cos(math.radians(40.7))
    px, py = lon * SLON, lat * SLAT
    cum = 0.0
    best_t = 0.0
    best_d = float("inf")
    total = 0.0
    for i in range(len(points) - 1):
        ax, ay = points[i][1] * SLON, points[i][0] * SLAT
        bx, by = points[i + 1][1] * SLON, points[i + 1][0] * SLAT
        seg = math.hypot(bx - ax, by - ay)
        if seg < 1e-6:
            continue
        t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / seg**2))
        d = math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))
        if d < best_d:
            best_d = d
            best_t = cum + t * seg
        cum += seg
    total = cum
    return best_t / total if total > 0 else 0.0

api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health() -> tuple:
    last_run = IngestRun.query.order_by(IngestRun.started_at.desc()).first()
    return jsonify(
        {
            "status": "ok",
            "last_ingest_run": last_run.to_dict() if last_run else None,
        }
    )


@api_bp.get("/stations")
def list_stations() -> tuple:
    stations = Station.query.all()
    return jsonify([s.to_dict() for s in stations])


@api_bp.get("/vehicles")
def list_vehicles() -> tuple:
    query = VehicleSnapshot.query
    route = request.args.get("route")
    if route:
        query = query.filter(VehicleSnapshot.route_id == route.upper())
    vehicles = query.all()
    return jsonify([v.to_dict() for v in vehicles])


@api_bp.get("/alerts")
def list_alerts() -> tuple:
    alerts = ServiceAlert.query.order_by(ServiceAlert.starts_at.desc()).all()
    return jsonify([a.to_dict() for a in alerts])


@api_bp.get("/route-segments")
def list_route_segments() -> tuple:
    """Line geometry for the map -- accumulated edges between adjacent
    stations on each route, derived from real stop sequences (see
    app/etl.py for why there's no static shapes.txt backing this).
    """
    segments = RouteSegment.query.all()
    return jsonify([s.to_dict() for s in segments])


@api_bp.get("/route-shapes")
def list_route_shapes() -> tuple:
    """Full GTFS polyline geometry for every subway route, seeded from the
    bundled shapes.txt. Each entry is one continuous polyline (shape_id) with
    its ordered lat/lon points. Multiple polylines per route_id are normal.
    """
    shapes = RouteShape.query.all()
    return jsonify([s.to_dict() for s in shapes])


@api_bp.get("/routes/<route_id>/stops")
def route_stops(route_id: str) -> tuple:
    """Ordered stop list per direction for a route, derived by projecting each
    station onto the route's GTFS shape polyline and sorting by arc-length.
    Also includes current vehicle positions.
    """
    rid = route_id.upper()

    segments = RouteSegment.query.filter_by(route_id=rid).all()
    if not segments:
        return jsonify({"error": "route not found"}), 404

    stop_ids = {seg.stop_id_a for seg in segments} | {seg.stop_id_b for seg in segments}
    stations = {s.stop_id: s for s in Station.query.filter(Station.stop_id.in_(stop_ids)).all()}

    shapes = RouteShape.query.filter_by(route_id=rid).all()
    shape_dirs = _shape_directions()

    # Pick one representative shape per direction_id (longest shape wins)
    best: dict[int, tuple[int, str, list]] = {}  # dir_id -> (point_count, headsign, points)
    for shape in shapes:
        did, headsign = shape_dirs.get(shape.shape_id, (0, ""))
        pts = json.loads(shape.points_json)
        prev = best.get(did)
        if prev is None or len(pts) > prev[0]:
            best[did] = (len(pts), headsign, pts)

    # Current vehicles by stop
    vehicles = VehicleSnapshot.query.filter_by(route_id=rid).all()
    vehicles_by_stop: dict[str, list] = {}
    for v in vehicles:
        if v.stop_id:
            vehicles_by_stop.setdefault(v.stop_id, []).append(v.to_dict())

    directions = []
    for did in sorted(best):
        _, headsign, pts = best[did]
        # Project every station onto this shape and sort by arc-length
        params = [(
            _project_onto_polyline(st.lat, st.lon, pts),
            sid,
        ) for sid, st in stations.items()]
        params.sort()

        # Deduplicate stops that project to nearly the same position
        filtered: list[tuple[float, str]] = []
        prev_t = -1.0
        for t, sid in params:
            if t - prev_t > 0.004:
                filtered.append((t, sid))
                prev_t = t

        stops = []
        for _, sid in filtered:
            st = stations[sid]
            stops.append({
                "stop_id": sid,
                "name": st.name,
                "lat": st.lat,
                "lon": st.lon,
                "vehicles": vehicles_by_stop.get(sid, []),
            })

        directions.append({
            "direction_id": did,
            "headsign": headsign,
            "stops": stops,
        })

    return jsonify({"route_id": rid, "directions": directions})


@api_bp.get("/stats/alerts-by-route")
def alerts_by_route() -> tuple:
    """Aggregated counts feeding the D3 bar chart: how many active alerts
    are currently affecting each route.
    """
    counts: dict[str, int] = {}
    for alert in ServiceAlert.query.all():
        for route in (alert.routes or "").split(","):
            route = route.strip()
            if route:
                counts[route] = counts.get(route, 0) + 1

    data = sorted(
        ({"route": route, "count": count} for route, count in counts.items()),
        key=lambda row: row["count"],
        reverse=True,
    )
    return jsonify(data)


@api_bp.post("/ingest/run")
def trigger_ingest() -> tuple:
    """Manual trigger for the ETL job, gated behind a shared secret. Useful
    as a fallback if the in-process scheduler isn't available (e.g. a
    serverless/cold-start hosting environment), or just for testing.
    """
    secret = current_app.config.get("INGEST_TRIGGER_SECRET")
    if secret and request.headers.get("X-Ingest-Secret") != secret:
        return jsonify({"error": "unauthorized"}), 401

    from app.etl import run_ingest

    run = run_ingest()
    status_code = 200 if run.status == "success" else 502
    return jsonify(run.to_dict()), status_code
