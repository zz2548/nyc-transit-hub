import requests
from google.transit import gtfs_realtime_pb2


def get_vehicle_positions():
    try:
        # Define the URL inside the function
        VEHICLE_FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"

        # Make the request
        response = requests.get(VEHICLE_FEED_URL)

        # Check if request was successful
        if response.status_code != 200:
            return [{"error": f"HTTP error: {response.status_code}"}]

        # Parse the protocol buffer response
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        # Debug information
        entity_types = {}
        for entity in feed.entity:
            if entity.HasField("trip_update"):
                entity_types["trip_update"] = entity_types.get("trip_update", 0) + 1
            if entity.HasField("vehicle"):
                entity_types["vehicle"] = entity_types.get("vehicle", 0) + 1
            if entity.HasField("alert"):
                entity_types["alert"] = entity_types.get("alert", 0) + 1

        # If no vehicle data, try getting trip updates instead
        vehicles = []

        if entity_types.get("vehicle", 0) > 0:
            # Original code for vehicle positions
            for entity in feed.entity:
                if entity.HasField("vehicle") and entity.vehicle.HasField("position"):
                    vehicle = entity.vehicle
                    vehicle_data = {
                        "latitude": vehicle.position.latitude,
                        "longitude": vehicle.position.longitude
                    }

                    # Handle optional fields safely
                    if vehicle.HasField("trip"):
                        vehicle_data["route_id"] = vehicle.trip.route_id
                        vehicle_data["start_time"] = vehicle.trip.start_time
                        vehicle_data["start_date"] = vehicle.trip.start_date

                    if vehicle.HasField("vehicle") and vehicle.vehicle.HasField("id"):
                        vehicle_data["vehicle_id"] = vehicle.vehicle.id

                    vehicles.append(vehicle_data)
        elif entity_types.get("trip_update", 0) > 0:
            # Fallback to trip updates if no vehicle positions
            for entity in feed.entity:
                if entity.HasField("trip_update") and entity.trip_update.HasField("trip"):
                    trip = entity.trip_update.trip
                    trip_data = {
                        "route_id": trip.route_id,
                        "start_time": trip.start_time,
                        "start_date": trip.start_date,
                        "trip_id": trip.trip_id,
                        "data_type": "trip_update"  # Indicate this is trip data, not vehicle
                    }
                    vehicles.append(trip_data)

        # Add debug information to response
        if not vehicles:
            return [{"error": "No vehicle or trip data found", "entity_types": entity_types}]
        else:
            # Add entity type counts as the first element
            vehicles.insert(0, {"info": "Data summary", "entity_types": entity_types})
            return vehicles

    except Exception as e:
        return [{"error": str(e)}]