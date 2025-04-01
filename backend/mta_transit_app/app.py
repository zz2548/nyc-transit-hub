from flask import Flask, jsonify, render_template
from google.transit import gtfs_realtime_pb2
import requests
import time
import random
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy
import os
# import redis
from datetime import datetime

db = SQLAlchemy()
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
    # app.redis = redis.from_url(app.config.get('REDIS_URL', 'redis://localhost:6379/0'))

    # Define routes
    @app.route("/")
    def home():
        return render_template('index.html')

    @app.route("/vehicles")
    def vehicles():
        try:
            # Check if data is cached in Redis
            # cached_data = app.redis.get('vehicles_data')
            # if cached_data:
            #    return jsonify(eval(cached_data))  # Convert string back to list/dict

            # Select feeds to process - either use all or pick 2 random ones
            feeds_to_use = list(MTA_FEEDS.values())

            results = []

            for url in feeds_to_use:
                # Fetch data from MTA API
                response = requests.get(url, timeout=1000)

                # Parse the protocol buffer
                feed = gtfs_realtime_pb2.FeedMessage()
                feed.ParseFromString(response.content)

                # Extract and transform data - process more entities
                for entity in feed.entity[:100]:
                    if entity.HasField("trip_update"):
                        trip = entity.trip_update.trip
                        trip_data = {
                            "type": "trip_update",
                            "id": entity.id,
                            "route_id": trip.route_id,
                            "trip_id": trip.trip_id,
                            "start_date": trip.start_date,
                            "stops": []
                        }

                        # Include first 3 stops for brevity
                        for i, stu in enumerate(entity.trip_update.stop_time_update[:3]):
                            arrival_time = None
                            if stu.HasField("arrival") and stu.arrival.HasField("time"):
                                arrival_time = stu.arrival.time
                                # Convert timestamp to readable time
                                readable_time = time.strftime('%H:%M:%S',
                                                              time.localtime(int(arrival_time)))
                                trip_data["stops"].append({
                                    "stop_id": stu.stop_id,
                                    "arrival_time": readable_time
                                })

                        results.append(trip_data)

                    elif entity.HasField("vehicle"):
                        if entity.vehicle.HasField("position"):
                            vehicle = entity.vehicle
                            vehicle_data = {
                                "type": "vehicle",
                                "id": entity.id,
                                "latitude": vehicle.position.latitude,
                                "longitude": vehicle.position.longitude
                            }

                            if vehicle.HasField("trip"):
                                vehicle_data["route_id"] = vehicle.trip.route_id
                                vehicle_data["trip_id"] = vehicle.trip.trip_id

                            results.append(vehicle_data)

            # Add feed source info to help with debugging
            results.insert(0, {
                "type": "info",
                "message": f"Data from {len(feeds_to_use)} MTA feeds",
                "feeds_used": [url.split('/')[-1] for url in feeds_to_use],
                "total_entities": len(results)
            })

            # Cache the results in Redis for 60 seconds
            # app.redis.setex('vehicles_data', 60, str(results))

            # Ensure all data is JSON serializable before returning
            return jsonify(results)

        except Exception as e:
            print(f"Error: {str(e)}")
            return jsonify([{"error": str(e)}])

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
        try:
            from models import VehiclePosition, Trip, Route

            # Check if tables exist before querying
            inspector = db.inspect(db.engine)
            if not (inspector.has_table("vehicle_position") and
                    inspector.has_table("trip") and
                    inspector.has_table("route")):
                return jsonify({
                    "error": "Database tables do not exist yet. Please run initialization first.",
                    "vehicle_positions": 0,
                    "trips": 0,
                    "routes": 0
                })

            vehicle_count = VehiclePosition.query.count()
            trip_count = Trip.query.count()
            route_count = Route.query.count()

            return jsonify({
                "vehicle_positions": vehicle_count,
                "trips": trip_count,
                "routes": route_count
            })
        except Exception as e:
            return jsonify({
                "error": f"Database error: {str(e)}",
                "vehicle_positions": 0,
                "trips": 0,
                "routes": 0
            })

    @app.route("/api/routes")
    def routes():
        from models import Route
        routes = Route.query.all()
        routes_data = [{
            "id": r.id,
            "short_name": r.short_name,
            "long_name": r.long_name,
            "type": r.type,
            "color": r.color,
            "is_active": r.is_active
        } for r in routes]

        return jsonify(routes_data)

    @app.route("/api/trip/<trip_id>")
    def trip_details(trip_id):
        from models import Trip, TripStop
        trip = Trip.query.get_or_404(trip_id)
        stops = TripStop.query.filter_by(trip_id=trip_id).order_by(TripStop.stop_sequence).all()

        trip_data = {
            "id": trip.id,
            "route_id": trip.route_id,
            "service_id": trip.service_id,
            "direction_id": trip.direction_id,
            "is_assigned": trip.is_assigned,
            "stops": [{
                "stop_id": stop.stop_id,
                "arrival_time": stop.arrival_time.strftime('%H:%M:%S') if stop.arrival_time else None,
                "departure_time": stop.departure_time.strftime('%H:%M:%S') if stop.departure_time else None,
                "sequence": stop.stop_sequence
            } for stop in stops]
        }

        return jsonify(trip_data)

    return app


def fetch_and_store_mta_data():
    from models import db, Route, Trip, VehiclePosition, Stop, TripStop

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
                            route_id=trip_update.trip.route_id,
                            service_id=trip_update.trip.start_date or "unknown",
                            direction_id=False,  # Default
                            is_assigned=True if hasattr(trip_update.trip, 'nyct_trip_descriptor') and
                                                trip_update.trip.nyct_trip_descriptor.is_assigned else False
                        )
                        db.session.add(new_trip)

                        # Process stop times for this trip
                        for i, stu in enumerate(trip_update.stop_time_update):
                            stop_id = stu.stop_id

                            # Check if stop exists
                            existing_stop = Stop.query.filter_by(id=stop_id).first()
                            if not existing_stop:
                                # Create a new stop with minimal info
                                new_stop = Stop(
                                    id=stop_id,
                                    name=f"Stop {stop_id}",
                                    latitude=0.0,  # Placeholder
                                    longitude=0.0  # Placeholder
                                )
                                db.session.add(new_stop)

                            # Create trip stop relationship
                            arrival_time = None
                            departure_time = None

                            if stu.HasField("arrival") and stu.arrival.HasField("time"):
                                arrival_time = datetime.fromtimestamp(stu.arrival.time)

                            if stu.HasField("departure") and stu.departure.HasField("time"):
                                departure_time = datetime.fromtimestamp(stu.departure.time)

                            trip_stop = TripStop(
                                trip_id=trip_id,
                                stop_id=stop_id,
                                stop_sequence=i,
                                arrival_time=arrival_time,
                                departure_time=departure_time
                            )
                            db.session.add(trip_stop)

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