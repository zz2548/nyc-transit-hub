"""
The ETL pipeline behind the resume bullet. Two jobs:

  seed_stations() -- runs once at startup. Loads the official MTA static
  GTFS stop reference (parent stations only) into the `stations` table.

  run_ingest()    -- runs on a recurring interval (APScheduler, see app/__init__.py).
  Pulls all 8 NYCT subway realtime feeds + the service-alerts feed, normalizes
  them, and persists the result. This is what makes the project an actual
  pipeline rather than a live passthrough: the database keeps a "right now"
  snapshot independent of whether anyone has the page open.

`trip_to_vehicle_record` is kept as a pure function (no I/O) so it can be
unit tested against a plain stub object instead of a live feed connection --
see tests/test_etl.py.
"""

import csv
import logging
import os
from datetime import datetime
from typing import Any

from nyct_gtfs import NYCTFeed

from app.extensions import db
from app.mta_alerts import fetch_alerts_feed_dict, parse_alerts_feed_dict
from app.models import IngestRun, ServiceAlert, Station, VehicleSnapshot

logger = logging.getLogger(__name__)

# One representative line per actual MTA feed -- e.g. "1" and "6" both point
# at the same A-division feed, so fetching both would just double-count it.
FEED_GROUPS = ["1", "A", "B", "G", "J", "N", "L", "SI"]

_STOPS_TXT_PATH = os.path.join(os.path.dirname(__file__), "data", "stops.txt")


def seed_stations() -> int:
    """Idempotently load parent stations (location_type == "1") from the
    bundled static GTFS stops.txt. Safe to call on every startup.
    """
    inserted = 0
    with open(_STOPS_TXT_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("location_type") != "1":
                continue  # skip direction-specific child stops (e.g. "101N")

            existing = db.session.get(Station, row["stop_id"])
            if existing is None:
                db.session.add(
                    Station(
                        stop_id=row["stop_id"],
                        name=row["stop_name"],
                        lat=float(row["stop_lat"]),
                        lon=float(row["stop_lon"]),
                    )
                )
                inserted += 1

    db.session.commit()
    return inserted


def trip_to_vehicle_record(trip: Any) -> dict[str, Any] | None:
    """Map one nyct-gtfs `Trip` (or any object with the same attributes --
    see the test stub) into a row for `VehicleSnapshot`. Trips that haven't
    departed their origin yet have no location, so they're skipped: there's
    nothing to plot on the map.
    """
    if not trip.underway:
        return None

    return {
        "trip_id": trip.trip_id,
        "route_id": trip.route_id,
        "direction": trip.direction,
        "headsign": trip.headsign_text,
        "stop_id": trip.location,
        "location_status": trip.location_status,
        "has_delay_alert": trip.has_delay_alert,
        "last_position_update": trip.last_position_update,
    }


def _ingest_vehicles() -> int:
    known_stop_ids = {row[0] for row in db.session.query(Station.stop_id).all()}
    records = []

    for group in FEED_GROUPS:
        try:
            feed = NYCTFeed(group)
        except Exception:  # network/parse errors on one feed shouldn't sink the run
            logger.exception("Failed to fetch feed group %s", group)
            continue

        for trip in feed.trips:
            record = trip_to_vehicle_record(trip)
            if record and record["stop_id"] in known_stop_ids:
                records.append(record)

    VehicleSnapshot.query.delete()
    db.session.bulk_insert_mappings(VehicleSnapshot, records)
    db.session.commit()
    return len(records)


def _ingest_alerts() -> int:
    feed_dict = fetch_alerts_feed_dict()
    records = parse_alerts_feed_dict(feed_dict)

    for record in records:
        alert = ServiceAlert.query.filter_by(external_id=record["external_id"]).first()
        if alert is None:
            alert = ServiceAlert(external_id=record["external_id"])
            db.session.add(alert)

        alert.header_text = record["header_text"]
        alert.routes = record["routes"]
        alert.starts_at = record["starts_at"]
        alert.ends_at = record["ends_at"]
        alert.last_seen_at = datetime.utcnow()

    db.session.commit()
    return len(records)


def run_ingest() -> IngestRun:
    """The recurring ETL job. Always commits an IngestRun row, even on
    failure, so /api/health has something honest to report.
    """
    run = IngestRun(status="running")
    db.session.add(run)
    db.session.commit()

    try:
        run.vehicle_count = _ingest_vehicles()
        run.alert_count = _ingest_alerts()
        run.status = "success"
    except Exception as exc:  # pragma: no cover - exercised via integration, not unit tests
        logger.exception("Ingest run failed")
        run.status = "error"
        run.error_message = str(exc)
    finally:
        run.finished_at = datetime.utcnow()
        db.session.commit()

    return run
