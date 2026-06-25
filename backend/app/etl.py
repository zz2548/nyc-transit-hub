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
from app.models import IngestRun, RouteSegment, ServiceAlert, Station, VehicleSnapshot

logger = logging.getLogger(__name__)

# One representative line per actual MTA feed -- e.g. "1" and "6" both point
# at the same A-division feed, so fetching both would just double-count it.
FEED_GROUPS = ["1", "A", "B", "G", "J", "N", "L", "SI"]

_STOPS_TXT_PATH = os.path.join(os.path.dirname(__file__), "data", "stops.txt")

_child_to_parent_cache: dict[str, str] | None = None


def _load_child_to_parent_map() -> dict[str, str]:
    """Build a lookup from directional child stop id (e.g. "228N", as
    reported by VehiclePosition.stop_id in the realtime feed) to its parent
    station id (e.g. "228", as stored in `Station`). Cached at module level
    since the static file never changes at runtime.
    """
    global _child_to_parent_cache
    if _child_to_parent_cache is not None:
        return _child_to_parent_cache

    mapping: dict[str, str] = {}
    with open(_STOPS_TXT_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            parent = row.get("parent_station")
            if parent:
                mapping[row["stop_id"]] = parent

    _child_to_parent_cache = mapping
    return mapping


def resolve_parent_stop_id(stop_id: str | None, child_to_parent: dict[str, str]) -> str | None:
    """Translate a feed-reported directional stop id to the parent station
    id it belongs to. Falls back to the input unchanged if it's already a
    parent id (or unrecognized) -- pure function, see tests/test_etl.py.
    """
    if stop_id is None:
        return None
    return child_to_parent.get(stop_id, stop_id)


def trip_to_segment_pairs(trip: Any, child_to_parent: dict[str, str]) -> list[tuple[str, str, str]]:
    """Derive (route_id, station_a, station_b) edges from one trip's stop
    sequence. There's no static `shapes.txt` bundled with nyct-gtfs (only
    stops.txt and trips.txt), so route line geometry is built from real
    operating data instead: each currently-scheduled trip's ordered stop
    list is a real, observed path along that route. Aggregated across many
    trips over several ingest cycles, the union of these edges converges on
    the full route shape -- see _ingest_route_segments().

    Pure function: takes any object exposing `.route_id` and
    `.stop_time_updates` (each with `.stop_id`) -- see tests/test_etl.py.
    """
    stop_ids = [resolve_parent_stop_id(update.stop_id, child_to_parent) for update in trip.stop_time_updates]

    pairs = []
    for a, b in zip(stop_ids, stop_ids[1:]):
        if a and b and a != b:
            pairs.append((trip.route_id, *sorted((a, b))))
    return pairs


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


def _fetch_live_trips() -> list[Any]:
    """Fetch all 8 NYCT feeds once and return a flat list of trips. Both
    vehicle positions and route-segment geometry are derived from this same
    fetch -- there's no reason to hit the MTA endpoint twice per cycle.
    """
    trips = []
    for group in FEED_GROUPS:
        try:
            feed = NYCTFeed(group)
        except Exception:  # network/parse errors on one feed shouldn't sink the run
            logger.exception("Failed to fetch feed group %s", group)
            continue
        trips.extend(feed.trips)
    return trips


def _ingest_vehicles(trips: list[Any], child_to_parent: dict[str, str], known_stop_ids: set[str]) -> int:
    records = []
    for trip in trips:
        record = trip_to_vehicle_record(trip)
        if not record:
            continue
        record["stop_id"] = resolve_parent_stop_id(record["stop_id"], child_to_parent)
        if record["stop_id"] in known_stop_ids:
            records.append(record)

    VehicleSnapshot.query.delete()
    db.session.bulk_insert_mappings(VehicleSnapshot, records)
    db.session.commit()
    return len(records)


def _ingest_route_segments(trips: list[Any], child_to_parent: dict[str, str], known_stop_ids: set[str]) -> int:
    """Unlike vehicles, segments accumulate rather than reset each cycle --
    a route's shape doesn't change minute to minute, so there's no reason
    to forget an edge just because this particular cycle didn't see a trip
    that crossed it. Over the first several cycles after a cold start, the
    line layer fills in as more of each route's real stop patterns are
    observed; see trip_to_segment_pairs() for why this approach exists at
    all instead of reading a static shapes.txt.
    """
    existing = {(s.route_id, s.stop_id_a, s.stop_id_b) for s in RouteSegment.query.all()}
    new_count = 0

    for trip in trips:
        for route_id, stop_a, stop_b in trip_to_segment_pairs(trip, child_to_parent):
            key = (route_id, stop_a, stop_b)
            if key in existing or stop_a not in known_stop_ids or stop_b not in known_stop_ids:
                continue
            existing.add(key)
            db.session.add(RouteSegment(route_id=route_id, stop_id_a=stop_a, stop_id_b=stop_b))
            new_count += 1

    db.session.commit()
    return new_count


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
        known_stop_ids = {row[0] for row in db.session.query(Station.stop_id).all()}
        child_to_parent = _load_child_to_parent_map()
        trips = _fetch_live_trips()

        run.vehicle_count = _ingest_vehicles(trips, child_to_parent, known_stop_ids)
        run.new_segment_count = _ingest_route_segments(trips, child_to_parent, known_stop_ids)
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
