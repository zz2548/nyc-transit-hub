"""
NYCT's service-alerts feed isn't covered by the `nyct-gtfs` library (which
focuses on trip/vehicle data), so we talk to it directly the same way the
original `api_example.py` proof-of-concept did: fetch the protobuf feed and
convert it to a plain dict with `MessageToDict`.

We reuse nyct_gtfs's own bundled compiled proto module rather than installing
the separate `gtfs-realtime-bindings` package: both define a proto file named
"gtfs-realtime.proto", and protobuf's global descriptor pool throws on
loading the same file twice in one process.

The fetch and the parse are split into two functions on purpose: `parse_alerts_feed_dict`
takes a plain dict and has no network dependency, so it can be unit tested directly
against a saved sample response (see tests/test_etl.py) without needing a live
connection to MTA.
"""

import datetime
from typing import Any

import requests
from google.protobuf.json_format import MessageToDict
from nyct_gtfs.compiled_gtfs import gtfs_realtime_pb2

ALERTS_FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"


def fetch_alerts_feed_dict(timeout: int = 15) -> dict[str, Any]:
    """Fetch and parse the live service-alerts feed. Requires network access
    to MTA's API endpoint -- not available from this sandbox, but works from
    any normal hosting environment (Render, a laptop, etc).
    """
    response = requests.get(ALERTS_FEED_URL, timeout=timeout)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return MessageToDict(feed)


def parse_alerts_feed_dict(feed_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn a parsed alerts FeedMessage dict into a flat list of records
    ready to upsert into `ServiceAlert`. Pure function -- no I/O.
    """
    records = []

    for entity in feed_dict.get("entity", []):
        alert = entity.get("alert")
        if alert is None:
            continue

        header = "N/A"
        translations = alert.get("headerText", {}).get("translation", [])
        for translation in translations:
            if translation.get("language") == "en":
                header = translation.get("text", "N/A")
                break
        else:
            if translations:
                header = translations[0].get("text", "N/A")

        routes = sorted(
            {
                informed.get("routeId")
                for informed in alert.get("informedEntity", [])
                if informed.get("routeId")
            }
        )

        active_period = (alert.get("activePeriod") or [{}])[0]
        starts_at = _epoch_to_datetime(active_period.get("start"))
        ends_at = _epoch_to_datetime(active_period.get("end"))

        records.append(
            {
                "external_id": entity["id"],
                "header_text": header,
                "routes": ",".join(routes),
                "starts_at": starts_at,
                "ends_at": ends_at,
            }
        )

    return records


def _epoch_to_datetime(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    return datetime.datetime.utcfromtimestamp(int(value))
