# backend/config.py — Application settings loaded from environment
"""
Centralized configuration using pydantic-settings.
All values loaded from .env file or environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings — auto-loaded from .env"""

    # ── App ───────────────────────────────────────────────────────────
    APP_NAME: str = "BhumiRaksha"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-to-a-secure-random-string"

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://bhumiraksha:password@localhost:5432/bhumiraksha"
    DATABASE_URL_SYNC: str = "postgresql://bhumiraksha:password@localhost:5432/bhumiraksha"

    # ── Redis ─────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Google Earth Engine ───────────────────────────────────────────
    GEE_PROJECT: str = "cropfire-gee"
    GEE_SERVICE_ACCOUNT: Optional[str] = None
    GEE_KEY_FILE: Optional[str] = None

    # ── ML Models ─────────────────────────────────────────────────────
    YOLO_MODEL_PATH: str = "./models/flood_yolov8m.pt"
    SEGFORMER_MODEL_PATH: str = "./models/segformer_b4_flood.pth"

    # ── SMS Provider ──────────────────────────────────────────────────
    SMS_PROVIDER: str = "msg91"  # msg91 | twilio
    MSG91_AUTH_KEY: Optional[str] = None
    MSG91_SENDER_ID: str = "BRAKSH"
    MSG91_TEMPLATE_ID: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None

    # ── PFMS ──────────────────────────────────────────────────────────
    PFMS_API_URL: str = "https://pfms.nic.in/api/v1"
    PFMS_API_KEY: Optional[str] = None
    PFMS_AGENCY_CODE: Optional[str] = None

    # ── File Storage ──────────────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── CORS ──────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # ── Officer Auth ──────────────────────────────────────────────────
    OFFICER_JWT_SECRET: str = "change-me-officer-jwt-secret"
    OFFICER_JWT_EXPIRY_HOURS: int = 24

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton settings instance
settings = Settings()
