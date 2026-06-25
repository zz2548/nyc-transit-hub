import os


def _normalize_db_url(url: str) -> str:
    """Render/Heroku-style providers hand out 'postgres://' URLs; SQLAlchemy
    2.x requires the 'postgresql://' scheme. Normalize so either works.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.environ.get("DATABASE_URL", "sqlite:///transit_hub.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # The in-process scheduler is what makes this an ETL *pipeline* rather
    # than a passthrough proxy: it polls MTA on an interval and persists
    # normalized snapshots, independent of whether anyone is viewing the UI.
    ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"
    INGEST_INTERVAL_SECONDS = int(os.environ.get("INGEST_INTERVAL_SECONDS", "30"))

    INGEST_TRIGGER_SECRET = os.environ.get("INGEST_TRIGGER_SECRET", "")


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    ENABLE_SCHEDULER = False
    TESTING = True
