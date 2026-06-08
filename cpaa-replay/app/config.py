import os

MAX_CONTENT_LENGTH = 256 * 1024


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required and must be set in the environment")
    return value


class Config:
    def __init__(self):
        self.SECRET_KEY = _require_env("SECRET_KEY")
        self.APP_PASSWORD = _require_env("APP_PASSWORD")
        self.LIVE_DB = _require_env("LIVE_DB")
        self.SHADOW_DB = _require_env("SHADOW_DB")
        self.MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
        self.SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"

    def as_dict(self) -> dict:
        return {
            "SECRET_KEY": self.SECRET_KEY,
            "APP_PASSWORD": self.APP_PASSWORD,
            "LIVE_DB": self.LIVE_DB,
            "SHADOW_DB": self.SHADOW_DB,
            "MAX_CONTENT_LENGTH": self.MAX_CONTENT_LENGTH,
            "SESSION_COOKIE_SECURE": self.SESSION_COOKIE_SECURE,
            "SESSION_COOKIE_HTTPONLY": self.SESSION_COOKIE_HTTPONLY,
            "SESSION_COOKIE_SAMESITE": self.SESSION_COOKIE_SAMESITE,
        }
