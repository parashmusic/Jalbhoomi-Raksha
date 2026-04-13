# backend/main.py — FastAPI application entry point
"""
BhumiRaksha — AI-Powered Flood Detection & Relief System

Main application that wires together:
  - API routes (claims, officer, health)
  - Database lifecycle (init, shutdown)
  - CORS middleware
  - Logging configuration
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys
import os

# Add backend dir to path for relative imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from database import init_db, close_db
from api.routes import health_router, claims_router, officer_router


# ── Logging Setup ────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    format=(
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)
logger.add(
    "logs/bhumiraksha.log",
    rotation="10 MB",
    retention="7 days",
    compression="gz",
    level="INFO",
)


# ── Lifespan ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("=" * 60)
    logger.info(f"{settings.APP_NAME} starting up...")
    logger.info(f"   Environment: {settings.APP_ENV}")
    logger.info(f"   Debug: {settings.DEBUG}")
    logger.info("=" * 60)

    # Create upload directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Initialize DB (only in dev — use Alembic migrations in prod)
    if settings.APP_ENV == "development":
        try:
            await init_db()
            logger.info("[OK] Database tables created")
        except Exception as e:
            logger.warning(f"[SKIP] Database init skipped: {e}")

    logger.info("[OK] API ready at http://localhost:8000")
    logger.info("[OK] Docs at http://localhost:8000/docs")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    logger.info("Database connections closed. Goodbye!")


# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="BhumiRaksha API",
    description=(
        "AI-powered flood detection and government compensation verification system. "
        "Satellite intelligence cross-validates community-reported damage — making "
        "relief faster, fairer, and fraud-proof across rural India."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────
app.include_router(health_router, prefix="/api/v1")
app.include_router(claims_router, prefix="/api/v1")
app.include_router(officer_router, prefix="/api/v1")


# ── Root ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    """API root — welcome message."""
    return {
        "name": settings.APP_NAME,
        "tagline": "Flood Detection & Relief System",
        "description": (
            "AI-powered dual verification (satellite + ground) for "
            "fair, fast, fraud-proof flood relief across rural India."
        ),
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
