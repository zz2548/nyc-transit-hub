from flask import Flask, jsonify, render_template
from google.transit import gtfs_realtime_pb2
import requests
import time
import random

app = Flask(__name__)

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


@app.route("/")
def home():
    return render_template('index.html')


@app.route("/vehicles")
def vehicles():
    try:
        # Select feeds to process - either use all or pick 2 random ones
        feeds_to_use = list(MTA_FEEDS.values())  # Use all feeds
        # feeds_to_use = random.sample(list(MTA_FEEDS.values()), 2)  # Use 2 random feeds

        results = []

        for url in feeds_to_use:
            # Fetch data from MTA API
            response = requests.get(url, timeout=1000)  # Reduced timeout for faster response

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

        return jsonify(results)

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify([{"error": str(e)}])


if __name__ == "__main__":
    app.run(debug=True)