import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.etl import trip_to_vehicle_record
from app.mta_alerts import parse_alerts_feed_dict

FIXTURES = Path(__file__).parent / "fixtures"


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
