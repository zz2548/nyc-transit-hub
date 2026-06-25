import atexit
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.extensions import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(daemon=True)


def create_app(config_object: type[Config] = Config) -> Flask:
    """Application factory. Wires together the DB, CORS, the API blueprint,
    and (outside of testing) the background ETL scheduler that keeps the
    database stocked with live MTA data.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from app.routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()
        from app.etl import seed_stations

        seed_stations()

    if app.config["ENABLE_SCHEDULER"] and not scheduler.running:
        from app.etl import run_ingest

        def _job() -> None:
            with app.app_context():
                run_ingest()

        scheduler.add_job(
            _job,
            "interval",
            seconds=app.config["INGEST_INTERVAL_SECONDS"],
            id="ingest_job",
            next_run_time=None,  # fire immediately on startup, see below
        )
        scheduler.start()
        # Kick off one ingest right away so the demo never opens to an empty DB
        scheduler.modify_job("ingest_job", next_run_time=datetime.now())
        atexit.register(lambda: scheduler.shutdown(wait=False))

    return app
