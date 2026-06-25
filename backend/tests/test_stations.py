from app.config import TestConfig
from app.extensions import db
from app.models import Station

import pytest

from app import create_app


@pytest.fixture
def app():
    flask_app = create_app(TestConfig)
    yield flask_app


def test_seed_stations_loads_only_parent_stations(app):
    with app.app_context():
        # create_app() already calls seed_stations() once on startup
        count = Station.query.count()

        # NYC subway has ~472 parent stations -- assert a sane range rather
        # than an exact number so this doesn't break if MTA opens a station
        assert 400 < count < 550

        grand_central = Station.query.filter_by(name="Grand Central-42 St").first()
        assert grand_central is not None
        assert -74.1 < grand_central.lon < -73.9  # sanity check it's in NYC
        assert 40.5 < grand_central.lat < 40.9


def test_seed_stations_is_idempotent(app):
    from app.etl import seed_stations

    with app.app_context():
        before = Station.query.count()
        inserted_again = seed_stations()
        after = Station.query.count()

        assert inserted_again == 0
        assert before == after
