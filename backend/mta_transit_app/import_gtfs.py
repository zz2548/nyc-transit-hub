import os
import csv
import zipfile
import requests
import sqlite3
from io import BytesIO
from db import get_db_connection, init_db

# URL for MTA's GTFS static data
MTA_GTFS_URL = "http://web.mta.info/developers/data/nyct/subway/google_transit.zip"


def download_gtfs_data():
    """Download the GTFS data from MTA website."""
    print("Downloading GTFS data...")
    response = requests.get(MTA_GTFS_URL)
    if response.status_code != 200:
        raise Exception(f"Failed to download GTFS data: {response.status_code}")

    return BytesIO(response.content)


def import_agency(conn, gtfs_folder):
    """Import agency data."""
    print("Importing agency data...")
    cursor = conn.cursor()

    with open(os.path.join(gtfs_folder, 'agency.txt'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                '''
                INSERT OR REPLACE INTO agency 
                (agency_id, agency_name, agency_url, agency_timezone, agency_lang, agency_phone)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    row.get('agency_id', ''),
                    row['agency_name'],
                    row['agency_url'],
                    row['agency_timezone'],
                    row.get('agency_lang', ''),
                    row.get('agency_phone', '')
                )
            )

    conn.commit()


def import_stops(conn, gtfs_folder):
    """Import stops data."""
    print("Importing stops data...")
    cursor = conn.cursor()

    with open(os.path.join(gtfs_folder, 'stops.txt'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                '''
                INSERT OR REPLACE INTO stops 
                (stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['stop_id'],
                    row['stop_name'],
                    float(row['stop_lat']) if row.get('stop_lat') else None,
                    float(row['stop_lon']) if row.get('stop_lon') else None,
                    int(row['location_type']) if row.get('location_type') else None,
                    row.get('parent_station', None)
                )
            )

    conn.commit()


def import_routes(conn, gtfs_folder):
    """Import routes data."""
    print("Importing routes data...")
    cursor = conn.cursor()

    with open(os.path.join(gtfs_folder, 'routes.txt'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                '''
                INSERT OR REPLACE INTO routes 
                (route_id, agency_id, route_short_name, route_long_name, route_desc, 
                route_type, route_url, route_color, route_text_color)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['route_id'],
                    row.get('agency_id', ''),
                    row.get('route_short_name', ''),
                    row.get('route_long_name', ''),
                    row.get('route_desc', ''),
                    int(row['route_type']),
                    row.get('route_url', ''),
                    row.get('route_color', ''),
                    row.get('route_text_color', '')
                )
            )

    conn.commit()


def import_calendar(conn, gtfs_folder):
    """Import calendar data."""
    print("Importing calendar data...")
    cursor = conn.cursor()

    with open(os.path.join(gtfs_folder, 'calendar.txt'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                '''
                INSERT OR REPLACE INTO calendar 
                (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['service_id'],
                    int(row['monday']),
                    int(row['tuesday']),
                    int(row['wednesday']),
                    int(row['thursday']),
                    int(row['friday']),
                    int(row['saturday']),
                    int(row['sunday']),
                    row['start_date'],
                    row['end_date']
                )
            )

    conn.commit()


def import_shapes(conn, gtfs_folder):
    """Import shapes data."""
    print("Importing shapes data...")
    cursor = conn.cursor()

    with open(os.path.join(gtfs_folder, 'shapes.txt'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        counter = 0

        # Begin transaction for batch inserts
        cursor.execute('BEGIN TRANSACTION')

        for row in reader:
            cursor.execute(
                '''
                INSERT INTO shapes 
                (shape_id, shape_pt_sequence, shape_pt_lat, shape_pt_lon)
                VALUES (?, ?, ?, ?)
                ''',
                (
                    row['shape_id'],
                    int(row['shape_pt_sequence']),
                    float(row['shape_pt_lat']),
                    float(row['shape_pt_lon'])
                )
            )

            counter += 1

            # Commit in batches for better performance
            if counter % 10000 == 0:
                conn.commit()
                cursor.execute('BEGIN TRANSACTION')
                print(f"Imported {counter} shape points...")

        # Commit any remaining shapes
        conn.commit()


def import_trips(conn, gtfs_folder):
    """Import trips data."""
    print("Importing trips data...")
    cursor = conn.cursor()

    with open(os.path.join(gtfs_folder, 'trips.txt'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        counter = 0

        # Begin transaction for batch inserts
        cursor.execute('BEGIN TRANSACTION')

        for row in reader:
            cursor.execute(
                '''
                INSERT OR REPLACE INTO trips 
                (trip_id, route_id, service_id, trip_headsign, direction_id, shape_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    row['trip_id'],
                    row['route_id'],
                    row['service_id'],
                    row.get('trip_headsign', ''),
                    int(row['direction_id']) if row.get('direction_id') else None,
                    row.get('shape_id', None)
                )
            )

            counter += 1

            # Commit in batches for better performance
            if counter % 10000 == 0:
                conn.commit()
                cursor.execute('BEGIN TRANSACTION')
                print(f"Imported {counter} trips...")

        # Commit any remaining trips
        conn.commit()


def import_stop_times(conn, gtfs_folder):
    """Import stop times data."""
    print("Importing stop times data...")
    cursor = conn.cursor()

    with open(os.path.join(gtfs_folder, 'stop_times.txt'), 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        counter = 0

        # Begin transaction for batch inserts
        cursor.execute('BEGIN TRANSACTION')

        for row in reader:
            cursor.execute(
                '''
                INSERT OR REPLACE INTO stop_times 
                (trip_id, stop_id, arrival_time, departure_time, stop_sequence)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    row['trip_id'],
                    row['stop_id'],
                    row.get('arrival_time', ''),
                    row.get('departure_time', ''),
                    int(row['stop_sequence'])
                )
            )

            counter += 1

            # Commit in batches for better performance
            if counter % 10000 == 0:
                conn.commit()
                cursor.execute('BEGIN TRANSACTION')
                print(f"Imported {counter} stop times...")

        # Commit any remaining stop times
        conn.commit()


def import_transfers(conn, gtfs_folder):
    """Import transfers data."""
    print("Importing transfers data...")
    try:
        cursor = conn.cursor()

        with open(os.path.join(gtfs_folder, 'transfers.txt'), 'r',
                  encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    '''
                    INSERT INTO transfers 
                    (from_stop_id, to_stop_id, transfer_type, min_transfer_time)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (
                        row['from_stop_id'],
                        row['to_stop_id'],
                        int(row['transfer_type']),
                        int(row.get('min_transfer_time', 0)) if row.get(
                            'min_transfer_time') else None
                    )
                )

        conn.commit()
    except FileNotFoundError:
        print("transfers.txt not found, skipping...")


def main():
    # Download GTFS data
    zip_file = download_gtfs_data()

    # Create a temporary directory for GTFS files
    temp_dir = "gtfs_temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Extract the zip file
    with zipfile.ZipFile(zip_file) as zip_ref:
        zip_ref.extractall(temp_dir)

    # Initialize the database
    init_db()

    # Import data
    conn = get_db_connection()
    try:
        import_agency(conn, temp_dir)
        import_stops(conn, temp_dir)
        import_routes(conn, temp_dir)
        import_calendar(conn, temp_dir)
        import_shapes(conn, temp_dir)
        import_trips(conn, temp_dir)
        import_stop_times(conn, temp_dir)
        import_transfers(conn, temp_dir)
        print("GTFS data import completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Error importing GTFS data: {e}")
    finally:
        conn.close()

        # Clean up temporary directory
        for file in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, file))
        os.rmdir(temp_dir)


if __name__ == "__main__":
    main()