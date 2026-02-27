import os
from datetime import timedelta


class Config:
    # =========================
    # Core
    # =========================
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # =========================
    # Database
    # =========================
    SQLALCHEMY_DATABASE_URI = "postgresql://Mark:Mark05%40Postgres@localhost:5432/zenithdb"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # =========================
    # JWT
    # =========================
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    # =========================
    # Debug
    # =========================
    DEBUG = os.getenv("FLASK_DEBUG", "True") == "True"
    BANK_NAME = "ZENITH"
    # Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False  
PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)