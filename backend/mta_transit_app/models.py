from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# User Management Models
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(64), nullable=True)
    preferred_language = db.Column(db.String(10), default='en')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    preferences = db.relationship('UserPreferences', backref='user', uselist=False, cascade='all, delete-orphan')
    saved_locations = db.relationship('SavedLocation', backref='user', lazy=True, cascade='all, delete-orphan')
    favorite_routes = db.relationship('FavoriteRoute', backref='user', lazy=True, cascade='all, delete-orphan')
    favorite_stations = db.relationship('FavoriteStation', backref='user', lazy=True, cascade='all, delete-orphan')
    alerts = db.relationship('Alert', backref='user', lazy=True, cascade='all, delete-orphan')
    search_history = db.relationship('SearchHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    trip_history = db.relationship('TripHistory', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class UserPreferences(db.Model):
    __tablename__ = 'user_preferences'

    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    dark_mode = db.Column(db.Boolean, default=False)
    notifications_enabled = db.Column(db.Boolean, default=True)
    push_notifications_enabled = db.Column(db.Boolean, default=True)
    email_notifications_enabled = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<UserPreferences for user {self.user_id}>'


class SavedLocation(db.Model):
    __tablename__ = 'saved_locations'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    type = db.Column(db.String(16), nullable=False)  # home/work/other
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<SavedLocation {self.name} for user {self.user_id}>'


# Favorites & Alerts Models
class FavoriteRoute(db.Model):
    __tablename__ = 'favorite_routes'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    route_id = db.Column(db.String(36), db.ForeignKey('routes.id'), nullable=False)
    nickname = db.Column(db.String(64), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)

    # Relationships
    route = db.relationship('Route', backref='favorited_by')

    def __repr__(self):
        return f'<FavoriteRoute {self.route_id} for user {self.user_id}>'


class FavoriteStation(db.Model):
    __tablename__ = 'favorite_stations'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    station_id = db.Column(db.String(36), db.ForeignKey('stops.id'), nullable=False)
    nickname = db.Column(db.String(64), nullable=True)
    notifications_enabled = db.Column(db.Boolean, default=True)

    # Relationships
    station = db.relationship('Stop', backref='favorited_by')

    def __repr__(self):
        return f'<FavoriteStation {self.station_id} for user {self.user_id}>'


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(16), nullable=False)  # route/station/system
    entity_id = db.Column(db.String(36), nullable=True)  # routeId or stationId
    conditions = db.Column(ARRAY(db.String), nullable=False)  # [delay, service_change, elevator_outage, etc]
    time_ranges = db.Column(JSON, nullable=True)  # Array of {days: [], startTime: Time, endTime: Time}

    def __repr__(self):
        return f'<Alert {self.id} for user {self.user_id}>'


# Transit Data Models
class Route(db.Model):
    __tablename__ = 'routes'

    id = db.Column(db.String(36), primary_key=True)
    short_name = db.Column(db.String(16), nullable=False)
    long_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    type = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(6), nullable=True)
    text_color = db.Column(db.String(6), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    agency_id = db.Column(db.String(36), nullable=True)

    # Relationships
    trips = db.relationship('Trip', backref='route', lazy=True)

    def __repr__(self):
        return f'<Route {self.short_name}>'


class Stop(db.Model):
    __tablename__ = 'stops'

    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    zone_id = db.Column(db.String(36), nullable=True)
    parent_station = db.Column(db.String(36), db.ForeignKey('stops.id'), nullable=True)
    wheelchair_boarding = db.Column(db.Boolean, default=False)

    # Relationships
    child_stops = db.relationship('Stop', backref=db.backref('parent', remote_side=[id]))
    accessibility_equipment = db.relationship('AccessibilityStatus', backref='station', lazy=True)

    def __repr__(self):
        return f'<Stop {self.name}>'


class Trip(db.Model):
    __tablename__ = 'trips'

    id = db.Column(db.String(36), primary_key=True)
    route_id = db.Column(db.String(36), db.ForeignKey('routes.id'), nullable=False)
    service_id = db.Column(db.String(36), nullable=False)
    direction_id = db.Column(db.Boolean, nullable=False)
    shape_id = db.Column(db.String(36), nullable=True)
    is_assigned = db.Column(db.Boolean, default=False)
    nyct_train_id = db.Column(db.String(36), nullable=True)

    # Relationships
    stops = db.relationship('TripStop', backref='trip', lazy=True, cascade='all, delete-orphan')
    vehicle_positions = db.relationship('VehiclePosition', backref='trip', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Trip {self.id} on route {self.route_id}>'


class TripStop(db.Model):
    __tablename__ = 'trip_stops'

    trip_id = db.Column(db.String(36), db.ForeignKey('trips.id'), primary_key=True)
    stop_id = db.Column(db.String(36), db.ForeignKey('stops.id'), primary_key=True)
    arrival_time = db.Column(db.DateTime, nullable=True)
    departure_time = db.Column(db.DateTime, nullable=True)
    stop_sequence = db.Column(db.Integer, primary_key=True)
    pickup_type = db.Column(db.Integer, nullable=True)
    drop_off_type = db.Column(db.Integer, nullable=True)
    scheduled_track = db.Column(db.String(8), nullable=True)
    actual_track = db.Column(db.String(8), nullable=True)

    # Relationships
    stop = db.relationship('Stop')

    def __repr__(self):
        return f'<TripStop for trip {self.trip_id} at stop {self.stop_id}>'


class ServiceAlert(db.Model):
    __tablename__ = 'service_alerts'

    id = db.Column(db.String(36), primary_key=True)
    active_from = db.Column(db.DateTime, nullable=False)
    active_to = db.Column(db.DateTime, nullable=True)
    affected_entities = db.Column(JSON, nullable=False)  # Array of {entityType: String, entityId: String}
    header_text = db.Column(db.String(255), nullable=False)
    description_text = db.Column(db.Text, nullable=True)
    cause = db.Column(db.String(64), nullable=True)
    effect = db.Column(db.String(64), nullable=True)
    url = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<ServiceAlert {self.id}>'


class VehiclePosition(db.Model):
    __tablename__ = 'vehicle_positions'

    id = db.Column(db.String(36), primary_key=True)
    trip_id = db.Column(db.String(36), db.ForeignKey('trips.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    current_stop_sequence = db.Column(db.Integer, nullable=True)
    current_stop_id = db.Column(db.String(36), db.ForeignKey('stops.id'), nullable=True)
    current_status = db.Column(db.String(16), nullable=True)  # STOPPED_AT, INCOMING_AT, IN_TRANSIT_TO
    congestion_level = db.Column(db.Integer, nullable=True)

    # Relationships
    current_stop = db.relationship('Stop')

    def __repr__(self):
        return f'<VehiclePosition for trip {self.trip_id}>'


class AccessibilityStatus(db.Model):
    __tablename__ = 'accessibility_status'

    equipment_id = db.Column(db.String(36), primary_key=True)
    station_id = db.Column(db.String(36), db.ForeignKey('stops.id'), nullable=False)
    equipment_type = db.Column(db.String(16), nullable=False)  # elevator/escalator
    is_operational = db.Column(db.Boolean, default=True)
    outage_reason = db.Column(db.String(255), nullable=True)
    estimated_return_to_service = db.Column(db.DateTime, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AccessibilityStatus {self.equipment_id} at station {self.station_id}>'


# Real-time Caching Models
class StationStatus(db.Model):
    __tablename__ = 'station_status'

    station_id = db.Column(db.String(36), db.ForeignKey('stops.id'), primary_key=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    crowd_level = db.Column(db.Integer, nullable=True)
    upcoming_arrivals = db.Column(JSON, nullable=True)  # Array of {routeId, tripId, direction, arrivalTime}
    alerts = db.Column(ARRAY(db.String), nullable=True)  # Array of alertIds

    # Relationships
    station = db.relationship('Stop')

    def __repr__(self):
        return f'<StationStatus for station {self.station_id}>'


class RouteStatus(db.Model):
    __tablename__ = 'route_status'

    route_id = db.Column(db.String(36), db.ForeignKey('routes.id'), primary_key=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(32), nullable=False)  # normal, delayed, service_change, planned_work
    alerts = db.Column(ARRAY(db.String), nullable=True)  # Array of alertIds

    # Relationships
    route = db.relationship('Route')

    def __repr__(self):
        return f'<RouteStatus for route {self.route_id}>'


class ServiceStatus(db.Model):
    __tablename__ = 'service_status'

    id = db.Column(db.String(36), primary_key=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subway = db.Column(JSON, nullable=True)  # {status: String, details: String}
    bus = db.Column(JSON, nullable=True)
    lirr = db.Column(JSON, nullable=True)
    metro_north = db.Column(JSON, nullable=True)
    bridges = db.Column(JSON, nullable=True)
    tunnels = db.Column(JSON, nullable=True)

    def __repr__(self):
        return f'<ServiceStatus {self.id}>'


# User Activity Models
class SearchHistory(db.Model):
    __tablename__ = 'search_history'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    query = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    result_count = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f'<SearchHistory {self.id} for user {self.user_id}>'


class TripHistory(db.Model):
    __tablename__ = 'trip_history'

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    origin_stop_id = db.Column(db.String(36), db.ForeignKey('stops.id'), nullable=False)
    destination_stop_id = db.Column(db.String(36), db.ForeignKey('stops.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    routes_used = db.Column(ARRAY(db.String), nullable=True)  # Array of routeIds

    # Relationships
    origin = db.relationship('Stop', foreign_keys=[origin_stop_id])
    destination = db.relationship('Stop', foreign_keys=[destination_stop_id])

    def __repr__(self):
        return f'<TripHistory {self.id} for user {self.user_id}>'