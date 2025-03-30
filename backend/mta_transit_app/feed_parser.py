import requests
import threading
import time
from google.transit import gtfs_realtime_pb2

URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"

latest_data = []  # Cache for latest data

def fetch_data():
    global latest_data
    try:
        response = requests.get(URL)
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        results = []
        for entity in feed.entity[:5]:  # Show first 5 entries
            if entity.HasField("trip_update"):
                trip = {
                    "trip_id": entity.trip_update.trip.trip_id,
                    "route_id": entity.trip_update.trip.route_id,
                    "stop_updates": []
                }
                for stu in entity.trip_update.stop_time_update:
                    arrival_time = stu.arrival.time if stu.HasField("arrival") else None
                    trip["stop_updates"].append({
                        "stop_id": stu.stop_id,
                        "arrival": arrival_time
                    })
                results.append(trip)
        latest_data = results
    except Exception as e:
        latest_data = [{"error": str(e)}]

def start_background_updater(interval=30):
    def run():
        while True:
            fetch_data()
            time.sleep(interval)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread  # Return thread so caller can manage it if needed

def get_subway_status():
    if not latest_data:  # If data hasn't been fetched yet
        fetch_data()     # Fetch it on demand
    return latest_data