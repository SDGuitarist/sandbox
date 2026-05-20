import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback')
    DATABASE = os.path.join('instance', 'venueconnect.db')


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
