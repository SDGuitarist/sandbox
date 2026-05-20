import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DATABASE = None  # Set in create_app based on instance_path
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB upload limit (CSV import)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour (default)
