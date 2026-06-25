from datetime import datetime

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import ServiceAlert, Station, RouteSegment, VehicleSnapshot


@pytest.fixture
def app():
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        # one known real station id from the seeded data, plus a fake live
        # vehicle and alert on top of it
        station = Station.query.filter_by(name="Times Sq-42 St").first()
        grand_central = Station.query.filter_by(name="Grand Central-42 St").first()
        assert station is not None
        assert grand_central is not None

        db.session.add(
            VehicleSnapshot(
                trip_id="121950_5..N",
                route_id="5",
                direction="N",
                headsign="Eastchester-Dyre Av",
                stop_id=station.stop_id,
                location_status="STOPPED_AT",
                has_delay_alert=False,
                last_position_update=datetime(2025, 3, 28, 12, 0, 0),
            )
        )
        db.session.add(
            ServiceAlert(
                external_id="lmm:alert:1",
                header_text="Test delay on the 5 train",
                routes="5,6",
                starts_at=datetime(2025, 3, 28, 11, 0, 0),
            )
        )
        db.session.add(
            RouteSegment(route_id="7", stop_id_a=grand_central.stop_id, stop_id_b=station.stop_id)
        )
        db.session.commit()

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_stations_endpoint_returns_seeded_data(client):
    resp = client.get("/api/stations")
    assert resp.status_code == 200
    stations = resp.get_json()
    assert len(stations) > 400
    assert {"stop_id", "name", "lat", "lon"} <= stations[0].keys()


def test_vehicles_endpoint_joins_station_position(client):
    resp = client.get("/api/vehicles")
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["route_id"] == "5"
    assert body[0]["station_name"] == "Times Sq-42 St"
    assert body[0]["lat"] is not None


def test_vehicles_endpoint_filters_by_route(client):
    assert len(client.get("/api/vehicles?route=5").get_json()) == 1
    assert len(client.get("/api/vehicles?route=Q").get_json()) == 0


def test_alerts_endpoint(client):
    body = client.get("/api/alerts").get_json()
    assert len(body) == 1
    assert body[0]["routes"] == ["5", "6"]


def test_alerts_by_route_aggregation(client):
    body = client.get("/api/stats/alerts-by-route").get_json()
    assert {"route": "5", "count": 1} in body
    assert {"route": "6", "count": 1} in body


def test_route_segments_endpoint_resolves_station_positions(client, app):
    body = client.get("/api/route-segments").get_json()
    assert len(body) == 1
    segment = body[0]
    assert segment["route_id"] == "7"

    with app.app_context():
        expected_ids = {
            Station.query.filter_by(name="Times Sq-42 St").first().stop_id,
            Station.query.filter_by(name="Grand Central-42 St").first().stop_id,
        }
    assert {segment["a"]["stop_id"], segment["b"]["stop_id"]} == expected_ids
    assert segment["a"]["lat"] is not None and segment["b"]["lon"] is not None


def test_manual_ingest_trigger_requires_secret_when_configured(client, app):
    app.config["INGEST_TRIGGER_SECRET"] = "shh"
    resp = client.post("/api/ingest/run")
    assert resp.status_code == 401
