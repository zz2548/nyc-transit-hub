import requests
import json
import time
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict


def test_mta_api_connection():
    """
    Test connection to the MTA API and fetch real-time subway information.
    No API key required.

    Requirements:
    - google-protobuf and gtfs-realtime-bindings packages installed
    """
    # MTA subway feed endpoints (list of available feeds)
    # From this page: https://api.mta.info/#/subwayRealTimeFeeds
    SUBWAY_FEEDS = {
        "A-C-E-Srockaway": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace",
        "G": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g",
        "N-Q-R-W": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw",
        "1-2-3-4-5-6-7-S": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs",
        "B-D-F-M-Sfranklin": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm",
        "J-Z": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz",
        "L": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l",
        "SIR": "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si"
    }

    # Service alerts feed endpoint
    ALERTS_FEED = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"

    # Test with "1-2-3-4-5-6-7-S" lines
    feed_url = SUBWAY_FEEDS["1-2-3-4-5-6-7-S"]

    try:
        # Make request to the API (no headers/API key needed)
        print(f"Making request to {feed_url}")
        response = requests.get(feed_url)

        # Check if request was successful
        if response.status_code == 200:
            print(f"Successfully connected to MTA API. Status code: {response.status_code}")
            print(f"Response size: {len(response.content)} bytes")

            # Parse the protocol buffer response
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)

            # Convert to Python dict for easier handling
            feed_dict = MessageToDict(feed)

            # Basic info about the feed
            header = feed_dict.get('header', {})
            print(f"\nFeed version: {header.get('gtfsRealtimeVersion', 'N/A')}")
            timestamp = header.get('timestamp', 0)
            if timestamp:
                timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(timestamp)))
                print(f"Timestamp: {timestamp} ({timestamp_str})")

            # Get number of entities in the feed
            entities = feed_dict.get('entity', [])
            print(f"Number of entities in feed: {len(entities)}")

            # Print details of the first few trip updates
            trip_updates = [e for e in entities if 'tripUpdate' in e]
            vehicle_positions = [e for e in entities if 'vehicle' in e]
            alerts = [e for e in entities if 'alert' in e]

            print(f"\nTrip updates: {len(trip_updates)}")
            print(f"Vehicle positions: {len(vehicle_positions)}")
            print(f"Service alerts: {len(alerts)}")

            # Sample of trip update data
            if trip_updates:
                sample_trip = trip_updates[0]
                trip_id = sample_trip.get('tripUpdate', {}).get('trip', {}).get('tripId', 'N/A')
                route_id = sample_trip.get('tripUpdate', {}).get('trip', {}).get('routeId', 'N/A')

                print(f"\nSample trip update:")
                print(f"Trip ID: {trip_id}")
                print(f"Route ID: {route_id}")

                # Print stop time updates
                stop_updates = sample_trip.get('tripUpdate', {}).get('stopTimeUpdate', [])
                if stop_updates:
                    print(f"Next stops ({len(stop_updates)}):")
                    for i, stop in enumerate(stop_updates[:3]):  # Print first 3 stops
                        stop_id = stop.get('stopId', 'N/A')
                        arrival = stop.get('arrival', {}).get('time', 'N/A')
                        if arrival != 'N/A':
                            arrival_time = time.strftime('%H:%M:%S', time.localtime(int(arrival)))
                        else:
                            arrival_time = 'N/A'

                        print(f"  {i + 1}. Stop ID: {stop_id}, Arrival: {arrival_time}")

            # Save a sample response to file for further analysis
            with open('mta_sample_response.json', 'w') as f:
                json.dump(feed_dict, f, indent=2)
            print("\nSaved sample response to 'mta_sample_response.json' for detailed analysis")

            # Now get the service alerts feed
            print(f"\n\nFetching service alerts from {ALERTS_FEED}")
            alerts_response = requests.get(ALERTS_FEED)

            if alerts_response.status_code == 200:
                print(f"Successfully connected to MTA Alerts API. Status code: {alerts_response.status_code}")
                print(f"Response size: {len(alerts_response.content)} bytes")

                # Parse the protocol buffer response
                alerts_feed = gtfs_realtime_pb2.FeedMessage()
                alerts_feed.ParseFromString(alerts_response.content)

                # Convert to Python dict for easier handling
                alerts_dict = MessageToDict(alerts_feed)

                # Basic info about the alerts feed
                alerts_header = alerts_dict.get('header', {})
                alerts_timestamp = alerts_header.get('timestamp', 0)
                if alerts_timestamp:
                    alerts_timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(alerts_timestamp)))
                    print(f"Alerts timestamp: {alerts_timestamp} ({alerts_timestamp_str})")

                # Get service alerts
                alert_entities = alerts_dict.get('entity', [])
                print(f"Number of service alerts: {len(alert_entities)}")

                # Sample some alerts
                if alert_entities:
                    print("\nSample service alerts:")
                    for i, alert_entity in enumerate(alert_entities[:3]):  # Print first 3 alerts
                        alert = alert_entity.get('alert', {})

                        # Get header text
                        header_text = "N/A"
                        if 'headerText' in alert:
                            translations = alert['headerText'].get('translation', [])
                            if translations:
                                header_text = translations[0].get('text', 'N/A')

                        # Get affected routes
                        affected_routes = []
                        for entity in alert.get('informedEntity', []):
                            if 'routeId' in entity:
                                affected_routes.append(entity['routeId'])

                        # Get time period
                        active_period = alert.get('activePeriod', [{}])[0]
                        start_time = "N/A"
                        end_time = "N/A"

                        if 'start' in active_period:
                            start_time = time.strftime('%Y-%m-%d %H:%M:%S',
                                                       time.localtime(int(active_period['start'])))

                        if 'end' in active_period:
                            end_time = time.strftime('%Y-%m-%d %H:%M:%S',
                                                     time.localtime(int(active_period['end'])))

                        print(f"\n  Alert {i + 1}:")
                        print(f"  Header: {header_text}")
                        print(f"  Affected routes: {', '.join(affected_routes) if affected_routes else 'N/A'}")
                        print(f"  Active period: {start_time} to {end_time}")

                # Save alerts to a separate file
                with open('mta_alerts_response.json', 'w') as f:
                    json.dump(alerts_dict, f, indent=2)
                print("\nSaved alerts response to 'mta_alerts_response.json' for detailed analysis")
            else:
                print(f"Failed to connect to MTA Alerts API. Status code: {alerts_response.status_code}")
                print(f"Response: {alerts_response.text}")

        else:
            print(f"Failed to connect to MTA API. Status code: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"Error testing MTA API: {str(e)}")


if __name__ == "__main__":
    test_mta_api_connection()