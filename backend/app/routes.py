from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models import IngestRun, RouteSegment, ServiceAlert, Station, VehicleSnapshot

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
