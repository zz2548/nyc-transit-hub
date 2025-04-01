import os
from datetime import timedelta


class Config:
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-development-only')
    DEBUG = False
    TESTING = False

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dev-jwt-key-for-development-only')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # MTA API Configuration
    MTA_API_KEY = os.environ.get('MTA_API_KEY')
    MTA_API_BASE_URL = 'https://api.mta.info/'

    # GTFS-realtime Poll Interval (in seconds)
    GTFS_RT_POLL_INTERVAL = 30  # Based on MTA GTFS-realtime specification

    # Redis Cache (for real-time data)
    # REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # App-specific settings
    LANGUAGES = ['en', 'es', 'zh', 'ru', 'ko', 'fr']  # Supported languages


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')


class ProductionConfig(Config):
    # Production-specific settings
    pass


# Configuration dictionary to easily select environment
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}