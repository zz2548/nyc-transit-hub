from flask import Flask, jsonify, render_template
from google.transit import gtfs_realtime_pb2
import requests
import time
import random
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_babel import Babel
import os
import redis

from models import db
from config import config

# MTA feed URLs
MTA_FEEDS = {
    "A-C-E-Srockaway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
    "G": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",
    "N-Q-R-W": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
    "1-2-3-4-5-6-7-S": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
    "B-D-F-M-Sfranklin": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
    "J-Z": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",
    "L": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l",
    "SIR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si"
}


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    jwt = JWTManager(app)
    babel = Babel(app)

    # Set up Redis for caching
    app.redis = redis.from_url(app.config.get('REDIS_URL', 'redis://localhost:6379/0'))

    # Define routes
    @app.route("/")
    def home():
        return render_template('index.html')

    @app.route("/vehicles")


    # Shell context for flask cli
    @app.shell_context_processor
    def make_shell_context():
        # Import all models here
        from models import (
            User, UserPreferences, SavedLocation,
            FavoriteRoute, FavoriteStation, Alert,
            Route, Stop, Trip, TripStop, ServiceAlert,
            VehiclePosition, AccessibilityStatus,
            StationStatus, RouteStatus, ServiceStatus,
            SearchHistory, TripHistory
        )

        return {
            'db': db,
            'User': User,
            'UserPreferences': UserPreferences,
            'SavedLocation': SavedLocation,
            'FavoriteRoute': FavoriteRoute,
            'FavoriteStation': FavoriteStation,
            'Alert': Alert,
            'Route': Route,
            'Stop': Stop,
            'Trip': Trip,
            'TripStop': TripStop,
            'ServiceAlert': ServiceAlert,
            'VehiclePosition': VehiclePosition,
            'AccessibilityStatus': AccessibilityStatus,
            'StationStatus': StationStatus,
            'RouteStatus': RouteStatus,
            'ServiceStatus': ServiceStatus,
            'SearchHistory': SearchHistory,
            'TripHistory': TripHistory
        }

    @app.route("/api/stats")
    def stats():
        from models import VehiclePosition, Trip, Route
        vehicle_count = VehiclePosition.query.count()
        trip_count = Trip.query.count()
        route_count = Route.query.count()

        return jsonify({
            "vehicle_positions": vehicle_count,
            "trips": trip_count,
            "routes": route_count
        })

    return app


def fetch_and_store_mta_data():
    from models import db, Route, Trip, VehiclePosition

    print("Fetching and storing MTA data...")

    try:
        # First, store basic route information
        for route_id, feed_url in MTA_FEEDS.items():
            # Check if route already exists
            existing_route = Route.query.filter_by(id=route_id).first()
            if not existing_route:
                # Create simplified route names from MTA keys
                route_name = route_id.replace('-', ' ').split(' ')[0]  # Just take the first part

                new_route = Route(
                    id=route_id,
                    short_name=route_name,
                    long_name=f"MTA {route_name} Line",
                    type=1,  # 1 = Subway
                    color="000000",  # Default black
                    is_active=True
                )
                db.session.add(new_route)

        # Commit route changes
        db.session.commit()
        print(f"Routes added/updated")

        # Now fetch vehicle data
        for route_id, feed_url in MTA_FEEDS.items():
            headers = {}
            if app.config.get('MTA_API_KEY'):
                headers['x-api-key'] = app.config.get('MTA_API_KEY')

            response = requests.get(feed_url, headers=headers, timeout=10)
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)

            for entity in feed.entity:
                if entity.HasField("trip_update"):
                    # Process trip info
                    trip_update = entity.trip_update
                    trip_id = trip_update.trip.trip_id

                    # Check if trip exists
                    existing_trip = Trip.query.filter_by(id=trip_id).first()
                    if not existing_trip:
                        new_trip = Trip(
                            id=trip_id,
                            route_id=route_id,
                            service_id=trip_update.trip.start_date or "unknown",
                            direction_id=False,  # Default
                            is_assigned=True if hasattr(trip_update.trip, 'nyct_trip_descriptor') and
                                                trip_update.trip.nyct_trip_descriptor.is_assigned else False
                        )
                        db.session.add(new_trip)

                if entity.HasField("vehicle"):
                    vehicle = entity.vehicle
                    if vehicle.HasField("trip") and vehicle.HasField("position"):
                        vehicle_id = f"{vehicle.trip.trip_id}_{int(time.time())}"

                        new_position = VehiclePosition(
                            id=vehicle_id,
                            trip_id=vehicle.trip.trip_id,
                            timestamp=datetime.fromtimestamp(vehicle.timestamp),
                            latitude=vehicle.position.latitude,
                            longitude=vehicle.position.longitude,
                            current_status=str(vehicle.current_status)
                        )
                        db.session.add(new_position)

        # Commit all changes
        db.session.commit()
        print("Vehicle data stored successfully")

    except Exception as e:
        db.session.rollback()
        print(f"Error storing MTA data: {str(e)}")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        fetch_and_store_mta_data()
    app.run(debug=True)