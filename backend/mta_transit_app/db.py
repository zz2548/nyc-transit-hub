import sqlite3
import os

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "instance", "gtfs.db")

# Create the instance directory if it doesn't exist
os.makedirs(os.path.dirname(db_path), exist_ok=True)


def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn


def init_db():
    """Initialize the database with GTFS schema."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables for static GTFS data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS agency (
        agency_id TEXT PRIMARY KEY,
        agency_name TEXT NOT NULL,
        agency_url TEXT NOT NULL,
        agency_timezone TEXT NOT NULL,
        agency_lang TEXT,
        agency_phone TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stops (
        stop_id TEXT PRIMARY KEY,
        stop_name TEXT,
        stop_lat REAL,
        stop_lon REAL,
        location_type INTEGER,
        parent_station TEXT,
        FOREIGN KEY (parent_station) REFERENCES stops (stop_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS routes (
        route_id TEXT PRIMARY KEY,
        agency_id TEXT,
        route_short_name TEXT,
        route_long_name TEXT,
        route_desc TEXT,
        route_type INTEGER,
        route_url TEXT,
        route_color TEXT,
        route_text_color TEXT,
        FOREIGN KEY (agency_id) REFERENCES agency (agency_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS calendar (
        service_id TEXT PRIMARY KEY,
        monday INTEGER NOT NULL,
        tuesday INTEGER NOT NULL,
        wednesday INTEGER NOT NULL,
        thursday INTEGER NOT NULL,
        friday INTEGER NOT NULL,
        saturday INTEGER NOT NULL,
        sunday INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shapes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shape_id TEXT,
        shape_pt_sequence INTEGER NOT NULL,
        shape_pt_lat REAL NOT NULL,
        shape_pt_lon REAL NOT NULL
    )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_shape_id ON shapes (shape_id)')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trips (
        trip_id TEXT PRIMARY KEY,
        route_id TEXT NOT NULL,
        service_id TEXT NOT NULL,
        trip_headsign TEXT,
        direction_id INTEGER,
        shape_id TEXT,
        FOREIGN KEY (route_id) REFERENCES routes (route_id),
        FOREIGN KEY (service_id) REFERENCES calendar (service_id),
        FOREIGN KEY (shape_id) REFERENCES shapes (shape_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stop_times (
        trip_id TEXT NOT NULL,
        stop_id TEXT NOT NULL,
        arrival_time TEXT,
        departure_time TEXT,
        stop_sequence INTEGER NOT NULL,
        PRIMARY KEY (trip_id, stop_sequence),
        FOREIGN KEY (trip_id) REFERENCES trips (trip_id),
        FOREIGN KEY (stop_id) REFERENCES stops (stop_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_stop_id TEXT,
        to_stop_id TEXT,
        transfer_type INTEGER NOT NULL,
        min_transfer_time INTEGER CHECK (min_transfer_time >= 0),
        FOREIGN KEY (from_stop_id) REFERENCES stops (stop_id),
        FOREIGN KEY (to_stop_id) REFERENCES stops (stop_id)
    )
    ''')

    # Create tables for real-time data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vehicle_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id TEXT,
        route_id TEXT,
        vehicle_id TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        bearing REAL,
        current_status INTEGER,
        stop_id TEXT,
        timestamp INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trip_id) REFERENCES trips (trip_id),
        FOREIGN KEY (route_id) REFERENCES routes (route_id),
        FOREIGN KEY (stop_id) REFERENCES stops (stop_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trip_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id TEXT,
        route_id TEXT,
        timestamp INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trip_id) REFERENCES trips (trip_id),
        FOREIGN KEY (route_id) REFERENCES routes (route_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stop_time_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_update_id INTEGER NOT NULL,
        stop_id TEXT,
        stop_sequence INTEGER,
        arrival_time INTEGER,
        departure_time INTEGER,
        schedule_relationship INTEGER,
        FOREIGN KEY (trip_update_id) REFERENCES trip_updates (id),
        FOREIGN KEY (stop_id) REFERENCES stops (stop_id)
    )
    ''')

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()