import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.etl import (
    _load_child_to_parent_map,
    resolve_parent_stop_id,
    trip_to_segment_pairs,
    trip_to_vehicle_record,
)
from app.mta_alerts import parse_alerts_feed_dict

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class FakeStopTimeUpdate:
    stop_id: str


@dataclass
class FakeTrip:
    """Stands in for nyct_gtfs.Trip in unit tests -- exposes the same
    attribute surface that trip_to_vehicle_record() actually reads, with
    no protobuf/network dependency.
    """

    underway: bool
    trip_id: str = "121950_5..N"
    route_id: str = "5"
    direction: str = "N"
    headsign_text: str = "Eastchester-Dyre Av"
    location: str = "228N"
    location_status: str = "STOPPED_AT"
    has_delay_alert: bool = False
    last_position_update: datetime = datetime(2025, 3, 28, 12, 0, 0)
    stop_time_updates: list[FakeStopTimeUpdate] = field(default_factory=list)


def test_trip_to_vehicle_record_skips_trips_not_yet_underway():
    assert trip_to_vehicle_record(FakeTrip(underway=False)) is None


def test_trip_to_vehicle_record_maps_underway_trip():
    record = trip_to_vehicle_record(FakeTrip(underway=True))

    assert record == {
        "trip_id": "121950_5..N",
        "route_id": "5",
        "direction": "N",
        "headsign": "Eastchester-Dyre Av",
        "stop_id": "228N",
        "location_status": "STOPPED_AT",
        "has_delay_alert": False,
        "last_position_update": datetime(2025, 3, 28, 12, 0, 0),
    }


def test_parse_alerts_feed_dict_against_real_sample():
    feed_dict = json.loads((FIXTURES / "mta_alerts_response.json").read_text())

    records = parse_alerts_feed_dict(feed_dict)

    assert len(records) == len(feed_dict["entity"])
    first = records[0]
    assert first["external_id"] == feed_dict["entity"][0]["id"]
    assert "A" in first["routes"]
    assert "Rockaway Blvd" in first["header_text"]
    assert first["starts_at"] is not None


def test_parse_alerts_feed_dict_handles_empty_feed():
    assert parse_alerts_feed_dict({"entity": []}) == []


def test_resolve_parent_stop_id_maps_directional_child_to_parent():
    # Real regression: the feed reports "228N" (a directional child stop),
    # but Station only stores parent ids like "228". Without this mapping,
    # every single vehicle silently failed to match and the map showed zero
    # trains despite the ETL run reporting "success".
    child_to_parent = _load_child_to_parent_map()

    assert resolve_parent_stop_id("228N", child_to_parent) == "228"
    assert resolve_parent_stop_id("127S", child_to_parent) == "127"


def test_resolve_parent_stop_id_passes_through_unknown_or_parent_ids():
    child_to_parent = _load_child_to_parent_map()

    assert resolve_parent_stop_id("228", child_to_parent) == "228"  # already a parent id
    assert resolve_parent_stop_id("not-a-real-stop", child_to_parent) == "not-a-real-stop"
    assert resolve_parent_stop_id(None, child_to_parent) is None


def test_trip_to_segment_pairs_derives_consecutive_edges():
    child_to_parent = _load_child_to_parent_map()
    trip = FakeTrip(
        underway=True,
        route_id="5",
        stop_time_updates=[
            FakeStopTimeUpdate(stop_id="228N"),
            FakeStopTimeUpdate(stop_id="137N"),
            FakeStopTimeUpdate(stop_id="132N"),
        ],
    )

    pairs = trip_to_segment_pairs(trip, child_to_parent)

    # Each pair is (route_id, *sorted(stop_a, stop_b)) -- order-independent
    # so the same physical edge from a southbound trip matches a northbound one.
    assert ("5", "137", "228") in pairs
    assert ("5", "132", "137") in pairs
    assert len(pairs) == 2  # 3 stops -> 2 consecutive edges


def test_trip_to_segment_pairs_skips_self_pairs_and_empty_sequences():
    child_to_parent = _load_child_to_parent_map()

    # A single-stop trip has no edges to form
    lone_stop = FakeTrip(underway=True, stop_time_updates=[FakeStopTimeUpdate(stop_id="228N")])
    assert trip_to_segment_pairs(lone_stop, child_to_parent) == []

    # Consecutive updates resolving to the same parent station (e.g. a
    # scheduled hold with separate arrival/departure rows) shouldn't
    # produce a zero-length self-edge
    same_station_twice = FakeTrip(
        underway=True,
        stop_time_updates=[FakeStopTimeUpdate(stop_id="228N"), FakeStopTimeUpdate(stop_id="228S")],
    )
    assert trip_to_segment_pairs(same_station_twice, child_to_parent) == []
