from datetime import datetime

from app.extensions import db


class Station(db.Model):
    """A subway station (parent stop), seeded once from MTA's static GTFS
    stops.txt. This is the map's base layer -- it never changes at runtime.
    """

    __tablename__ = "stations"

    stop_id = db.Column(db.String(16), primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)

    def to_dict(self) -> dict:
        return {
            "stop_id": self.stop_id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
        }


class VehicleSnapshot(db.Model):
    """The most recently observed position of one in-service train.

    NYCT's realtime feed doesn't publish GPS coordinates for subway cars --
    only the stop a train is currently at/approaching/departing. We record
    that directly and let the API join it to `Station` for a map-friendly
    lat/lon. The table is fully replaced on every ETL run (see etl.py),
    so it always reflects "right now", not history.
    """

    __tablename__ = "vehicle_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.String(64), nullable=False, index=True)
    route_id = db.Column(db.String(8), nullable=False, index=True)
    direction = db.Column(db.String(1))  # "N" or "S"
    headsign = db.Column(db.String(128))
    stop_id = db.Column(db.String(16), db.ForeignKey("stations.stop_id"), index=True)
    location_status = db.Column(db.String(16))  # INCOMING_AT / STOPPED_AT / IN_TRANSIT_TO
    has_delay_alert = db.Column(db.Boolean, default=False)
    last_position_update = db.Column(db.DateTime)
    observed_at = db.Column(db.DateTime, default=datetime.utcnow)

    station = db.relationship("Station")

    def to_dict(self) -> dict:
        return {
            "trip_id": self.trip_id,
            "route_id": self.route_id,
            "direction": self.direction,
            "headsign": self.headsign,
            "stop_id": self.stop_id,
            "station_name": self.station.name if self.station else None,
            "lat": self.station.lat if self.station else None,
            "lon": self.station.lon if self.station else None,
            "location_status": self.location_status,
            "has_delay_alert": self.has_delay_alert,
            "last_position_update": (
                self.last_position_update.isoformat() if self.last_position_update else None
            ),
        }


class ServiceAlert(db.Model):
    """An active MTA service alert, upserted by external alert id on every
    ETL run so we keep one row per alert instead of growing unbounded.
    """

    __tablename__ = "service_alerts"

    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(64), unique=True, nullable=False)
    header_text = db.Column(db.Text, nullable=False)
    routes = db.Column(db.String(128))  # comma-separated route ids
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime, nullable=True)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.external_id,
            "header_text": self.header_text,
            "routes": self.routes.split(",") if self.routes else [],
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
        }


class RouteSegment(db.Model):
    """One edge between two adjacent stations on a route, used to draw the
    colored line geometry on the map. There's no static `shapes.txt` in the
    bundled GTFS data (only stops.txt and trips.txt), so these edges are
    derived from real trips' observed stop sequences (see
    etl.trip_to_segment_pairs) and accumulated across ingest cycles rather
    than replaced each run -- a route's physical shape doesn't change
    minute to minute, so there's no reason to forget edges between runs.
    """

    __tablename__ = "route_segments"
    __table_args__ = (db.UniqueConstraint("route_id", "stop_id_a", "stop_id_b", name="uq_route_segment"),)

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.String(8), nullable=False, index=True)
    stop_id_a = db.Column(db.String(16), db.ForeignKey("stations.stop_id"), nullable=False)
    stop_id_b = db.Column(db.String(16), db.ForeignKey("stations.stop_id"), nullable=False)
    first_seen_at = db.Column(db.DateTime, default=datetime.utcnow)

    station_a = db.relationship("Station", foreign_keys=[stop_id_a])
    station_b = db.relationship("Station", foreign_keys=[stop_id_b])

    def to_dict(self) -> dict:
        return {
            "route_id": self.route_id,
            "a": {"stop_id": self.station_a.stop_id, "lat": self.station_a.lat, "lon": self.station_a.lon},
            "b": {"stop_id": self.station_b.stop_id, "lat": self.station_b.lat, "lon": self.station_b.lon},
        }


class RouteShape(db.Model):
    """One GTFS shape (a continuous polyline of lat/lon points) for a subway
    route, seeded once from the MTA static shapes.txt + trips.txt files.
    Multiple shapes per route are normal -- each direction/variant gets its
    own shape_id and row.
    """

    __tablename__ = "route_shapes"

    shape_id = db.Column(db.String(64), primary_key=True)
    route_id = db.Column(db.String(8), nullable=False, index=True)
    points_json = db.Column(db.Text, nullable=False)  # JSON [[lat, lon], ...]

    def to_dict(self) -> dict:
        import json

        return {
            "route_id": self.route_id,
            "shape_id": self.shape_id,
            "points": json.loads(self.points_json),
        }


class IngestRun(db.Model):
    """Observability log for the ETL pipeline -- proof the background job is
    actually running, and a place to see failures without reading server logs.
    """

    __tablename__ = "ingest_runs"

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)
    vehicle_count = db.Column(db.Integer, default=0)
    alert_count = db.Column(db.Integer, default=0)
    new_segment_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(16), default="running")  # running / success / error
    error_message = db.Column(db.Text)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "vehicle_count": self.vehicle_count,
            "alert_count": self.alert_count,
            "new_segment_count": self.new_segment_count,
            "status": self.status,
            "error_message": self.error_message,
        }
