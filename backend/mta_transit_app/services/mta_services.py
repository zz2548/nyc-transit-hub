import requests
import time
from datetime import datetime
import uuid
import json
import logging
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict

from models import (
    db, Route, Stop, Trip, TripStop, ServiceAlert,
    VehiclePosition, StationStatus, RouteStatus, ServiceStatus
)


class MTAService:
    """
    Service to interact with the MTA GTFS-realtime API and update the database
    with real-time transit information.
    """

    def __init__(self, app=None):
        self.app = app
        self.logger = logging.getLogger(__name__)

        if app:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        self.api_key = app.config['MTA_API_KEY']
        self.base_url = app.config['MTA_API_BASE_URL']
        self.poll_interval = app.config['GTFS_RT_POLL_INTERVAL']

        # Setup scheduler for periodic updates
        # Could use APScheduler or Celery here

    def fetch_gtfs_realtime(self, feed_id):
        """
        Fetch GTFS-realtime data from the MTA API

        Args:
            feed_id: The ID of the feed to fetch (e.g., '1' for 1,2,3,4,5,6 lines)

        Returns:
            A FeedMessage object from the gtfs_realtime_pb2 module
        """
        url = f"{self.base_url}/gtfs-realtime/nyct/{feed_id}"
        headers = {'x-api-key': self.api_key}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)

            return feed
        except Exception as e:
            self.logger.error(f"Error fetching GTFS-realtime feed {feed_id}: {str(e)}")
            return None

    def process_trip_updates(self, feed):
        """
        Process trip updates from the GTFS-realtime feed

        Args:
            feed: A FeedMessage object from the gtfs_realtime_pb2 module
        """
        try:
            for entity in feed.entity:
                if entity.HasField('trip_update'):
                    trip_update = entity.trip_update

                    # Check if trip exists, create if not
                    trip = Trip.query.get(trip_update.trip.trip_id)
                    if not trip:
                        trip = Trip(
                            id=trip_update.trip.trip_id,
                            route_id=trip_update.trip.route_id,
                            service_id=trip_update.trip.start_date,
                            direction_id=trip_update.trip.nyct_trip_descriptor.direction == 1,
                            # 1 for NORTH, 3 for SOUTH
                            is_assigned=trip_update.trip.nyct_trip_descriptor.is_assigned,
                            nyct_train_id=trip_update.trip.nyct_trip_descriptor.train_id
                        )
                        db.session.add(trip)
                    else:
                        # Update trip information
                        trip.is_assigned = trip_update.trip.nyct_trip_descriptor.is_assigned
                        trip.nyct_train_id = trip_update.trip.nyct_trip_descriptor.train_id

                    # Process stop time updates
                    for stop_update in trip_update.stop_time_update:
                        # NYCT format: Combined parent station ID and direction (N/S)
                        stop_id = stop_update.stop_id[:-1]  # Remove direction suffix

                        # Check if stop exists in trip
                        trip_stop = TripStop.query.filter_by(
                            trip_id=trip.id,
                            stop_id=stop_id
                        ).first()

                        if not trip_stop:
                            # Create new trip stop
                            trip_stop = TripStop(
                                trip_id=trip.id,
                                stop_id=stop_id,
                                stop_sequence=stop_update.stop_sequence
                            )
                            db.session.add(trip_stop)

                        # Update arrival/departure times
                        if stop_update.HasField('arrival'):
                            trip_stop.arrival_time = datetime.fromtimestamp(stop_update.arrival.time)

                        if stop_update.HasField('departure'):
                            trip_stop.departure_time = datetime.fromtimestamp(stop_update.departure.time)

                        # NYCT extension for track information
                        if stop_update.HasField('nyct_stop_time_update'):
                            trip_stop.scheduled_track = stop_update.nyct_stop_time_update.scheduled_track
                            trip_stop.actual_track = stop_update.nyct_stop_time_update.actual_track

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error processing trip updates: {str(e)}")

    def process_vehicle_positions(self, feed):
        """
        Process vehicle positions from the GTFS-realtime feed

        Args:
            feed: A FeedMessage object from the gtfs_realtime_pb2 module
        """
        try:
            for entity in feed.entity:
                if entity.HasField('vehicle'):
                    vehicle = entity.vehicle

                    # Check if vehicle position exists, update or create
                    vp = VehiclePosition.query.filter_by(trip_id=vehicle.trip.trip_id).first()

                    if not vp:
                        vp = VehiclePosition(
                            id=str(uuid.uuid4()),
                            trip_id=vehicle.trip.trip_id,
                            timestamp=datetime.fromtimestamp(vehicle.timestamp),
                            current_stop_sequence=vehicle.current_stop_sequence,
                            current_stop_id=vehicle.stop_id,
                            current_status=vehicle.current_status
                        )
                        db.session.add(vp)
                    else:
                        vp.timestamp = datetime.fromtimestamp(vehicle.timestamp)
                        vp.current_stop_sequence = vehicle.current_stop_sequence
                        vp.current_stop_id = vehicle.stop_id
                        vp.current_status = vehicle.current_status

                    # Add position if available
                    if vehicle.HasField('position'):
                        vp.latitude = vehicle.position.latitude
                        vp.longitude = vehicle.position.longitude

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error processing vehicle positions: {str(e)}")

    def process_alerts(self, feed):
        """
        Process alerts from the GTFS-realtime feed

        Args:
            feed: A FeedMessage object from the gtfs_realtime_pb2 module
        """
        try:
            for entity in feed.entity:
                if entity.HasField('alert'):
                    alert = entity.alert

                    # Create a unique ID for the alert
                    alert_id = f"alert_{entity.id}"

                    # Check if alert exists
                    service_alert = ServiceAlert.query.get(alert_id)

                    if not service_alert:
                        # Extract affected entities
                        affected_entities = []
                        for informed_entity in alert.informed_entity:
                            entity_dict = {}
                            if informed_entity.HasField('trip'):
                                entity_dict['entityType'] = 'trip'
                                entity_dict['entityId'] = informed_entity.trip.trip_i