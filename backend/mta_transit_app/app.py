from flask import Flask, render_template, jsonify, request
import os
import requests
import json
import time
from google.transit import gtfs_realtime_pb2
from db import get_db_connection

# Load environment variables

app = Flask(__name__)



# MTA subway feed URLs by line
# Shuttle special naming:
# H: Rockaway park shuttle, denoted as Sr on mta.info
# 0: 42nd St Shuttle, denoted as S on mta.info
# S: Franklin avenue shuttle, denoted as Sf on mta.info
MTA_FEEDS = {
    'A-C-E-H': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace',
    'B-D-F-M-S': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm',
    '1-2-3-4-5-6-7-0': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs',
    'G': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g',
    'J-Z': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz',
    'L': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l',
    'N-Q-R-W': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw',
    'SI': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si',
}

# Map route_id prefixes to their feed
ROUTE_TO_FEED = {
    'A': 'A-C-E-H', 'C': 'A-C-E-H', 'E': 'A-C-E-H', 'H': 'A-C-E-H',
    'B': 'B-D-F-M-S', 'D': 'B-D-F-M-S', 'F': 'B-D-F-M-S', 'M': 'B-D-F-M-S',
    'S': 'B-D-F-M-S',
    '1': '1-2-3-4-5-6-7-0', '2': '1-2-3-4-5-6-7-0', '3': '1-2-3-4-5-6-7-0',
    '4': '1-2-3-4-5-6-7-0', '5': '1-2-3-4-5-6-7-0', '6': '1-2-3-4-5-6-7-0',
    '7': '1-2-3-4-5-6-7-0', '0': '1-2-3-4-5-6-7-0',
    'G': 'G',
    'J': 'J-Z', 'Z': 'J-Z',
    'L': 'L',
    'N': 'N-Q-R-W', 'Q': 'N-Q-R-W', 'R': 'N-Q-R-W', 'W': 'N-Q-R-W',
    'SI': 'SI',
}


def fetch_realtime_data(feed_url):
    """Fetch real-time data from MTA API."""
    try:
        response = requests.get(feed_url)
        app.logger.info(f"Response status: {response.status_code}")
        app.logger.debug(f"Response headers: {response.headers}")
        app.logger.debug(f"Response length: {len(response.content)} bytes")

        if response.status_code != 200:
            app.logger.error(f"Failed to fetch data: {response.status_code}")
            return None

        feed = gtfs_realtime_pb2.FeedMessage()
        try:
            feed.ParseFromString(response.content)
            return feed
        except Exception as e:
            app.logger.error(f"Error parsing feed content: {e}")
            # Log a sample of the content
            app.logger.debug(f"Content sample: {response.content[:100]}")
            return None
    except Exception as e:
        app.logger.error(f"Error fetching real-time data: {e}")
        return None


def get_vehicle_positions(feed):
    if not feed:
        return []

    # Count entity types for diagnostics
    entity_counts = {'vehicle': 0, 'trip_update': 0, 'alert': 0, 'other': 0}
    for entity in feed.entity:
        if entity.HasField('vehicle'):
            entity_counts['vehicle'] += 1
        elif entity.HasField('trip_update'):
            entity_counts['trip_update'] += 1
        elif entity.HasField('alert'):
            entity_counts['alert'] += 1
        else:
            entity_counts['other'] += 1

    app.logger.info(f"Entity counts: {entity_counts}")

    # Rest of your function...

    vehicles = []
    timestamp = feed.header.timestamp

    for entity in feed.entity:
        if entity.HasField('vehicle'):
            vehicle = entity.vehicle

            # Skip if no position data
            if not vehicle.HasField('position'):
                continue

            vehicles.append({
                'trip_id': vehicle.trip.trip_id if vehicle.HasField('trip') else None,
                'route_id': vehicle.trip.route_id if vehicle.HasField('trip') else None,
                'lat': vehicle.position.latitude,
                'lon': vehicle.position.longitude,
                'bearing': vehicle.position.bearing if vehicle.position.HasField(
                    'bearing') else None,
                'status': vehicle.current_status,
                'stop_id': vehicle.stop_id if vehicle.HasField('stop_id') else None,
                'timestamp': timestamp
            })

    return vehicles


def save_vehicle_positions(vehicles):
    """Save vehicle positions to database."""
    if not vehicles:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('BEGIN TRANSACTION')

        # Clear old positions that are older than 10 minutes
        ten_minutes_ago = int(time.time()) - 600
        cursor.execute('DELETE FROM vehicle_positions WHERE timestamp < ?',
                       (ten_minutes_ago,))

        # Insert new positions
        for vehicle in vehicles:
            cursor.execute(
                '''
                INSERT INTO vehicle_positions 
                (trip_id, route_id, latitude, longitude, bearing, current_status, stop_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    vehicle['trip_id'],
                    vehicle['route_id'],
                    vehicle['lat'],
                    vehicle['lon'],
                    vehicle['bearing'],
                    vehicle['status'],
                    vehicle['stop_id'],
                    vehicle['timestamp']
                )
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error saving vehicle positions: {e}")
    finally:
        conn.close()


@app.route('/')
def index():
    """Main page showing all train lines."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT route_id, route_short_name, route_long_name, route_color FROM routes')
        routes = cursor.fetchall()

        route_data = [{
            'route_id': route['route_id'],
            'route_short_name': route['route_short_name'] or route['route_id'],
            'route_long_name': route['route_long_name'],
            'route_color': route['route_color'] or 'FF0000'
            # Default to red if no color
        } for route in routes]
    finally:
        conn.close()

    return render_template('index.html', routes=route_data)


@app.route('/api/trains', methods=['GET'])
def all_trains():
    """API endpoint to get all trains currently in service."""
    all_vehicles = []

    for feed_id, feed_url in MTA_FEEDS.items():
        feed = fetch_realtime_data(feed_url)
        if feed:
            vehicles = get_vehicle_positions(feed)
            all_vehicles.extend(vehicles)

            # Save vehicle positions to the database
            save_vehicle_positions(vehicles)

    return jsonify(all_vehicles)


@app.route('/api/trains/<route_id>', methods=['GET'])
def get_trains_by_route(route_id):
    """API endpoint to get trains for a specific route."""
    # Find the correct feed URL for this route
    route_prefix = route_id[0].upper()  # Get first character
    feed_id = ROUTE_TO_FEED.get(route_prefix)

    if not feed_id:
        return jsonify({"error": f"No feed found for route {route_id}"}), 404

    feed_url = MTA_FEEDS.get(feed_id)
    feed = fetch_realtime_data(feed_url)

    if not feed:
        return jsonify({"error": "Failed to fetch real-time data"}), 500

    vehicles = get_vehicle_positions(feed)
    app.logger.info(f"Total vehicles before filtering: {len(vehicles)}")

    # Filter for the specific route_id
    route_vehicles = [v for v in vehicles if
                      v['route_id'] and v['route_id'].startswith(route_id)]

    app.logger.info(f"Vehicles for route {route_id}: {len(route_vehicles)}")

    # Get additional stop information
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for vehicle in route_vehicles:
            if vehicle['stop_id']:
                cursor.execute('SELECT stop_name FROM stops WHERE stop_id = ?',
                               (vehicle['stop_id'],))
                stop = cursor.fetchone()
                if stop:
                    vehicle['stop_name'] = stop['stop_name']
    finally:
        conn.close()

    # Save vehicle positions to the database
    save_vehicle_positions(route_vehicles)

    return jsonify(route_vehicles)


@app.route('/train/<route_id>')
def train_map(route_id):
    """Page to display map for a specific train line."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Get route info
        cursor.execute('SELECT * FROM routes WHERE route_id = ?', (route_id,))
        route = cursor.fetchone()

        if not route:
            return "Route not found", 404

        route_data = {
            'route_id': route['route_id'],
            'route_short_name': route['route_short_name'] or route['route_id'],
            'route_long_name': route['route_long_name'],
            'route_color': route['route_color'] or "FF0000"
            # Default to red if no color
        }

        # Get all stops for this route
        cursor.execute('''
            SELECT DISTINCT s.stop_id, s.stop_name, s.stop_lat, s.stop_lon
            FROM stops s
            JOIN stop_times st ON s.stop_id = st.stop_id
            JOIN trips t ON st.trip_id = t.trip_id
            WHERE t.route_id = ? AND s.location_type = 0
        ''', (route_id,))

        stops = [{
            'stop_id': stop['stop_id'],
            'stop_name': stop['stop_name'],
            'lat': stop['stop_lat'],
            'lon': stop['stop_lon']
        } for stop in cursor.fetchall()]

    finally:
        conn.close()

    return render_template('map.html', route=route_data, stops=json.dumps(stops))


if __name__ == '__main__':
    app.run(debug=True)