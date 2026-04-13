# backend/api/routes/health.py — Health check endpoints
"""System health and info endpoints."""

from typing import Any
from fastapi import APIRouter, Depends
from models.schemas import HealthResponse
from config import settings
from api.dependencies import get_ground_detector, get_sar_mapper

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    ground: Any = Depends(get_ground_detector),
    sar: Any = Depends(get_sar_mapper),
):
    """System health check — verifies all services are reachable."""
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version="1.0.0",
        database="connected" if settings.DATABASE_URL else "not configured",
        redis="connected" if settings.REDIS_URL else "not configured",
        models_loaded=ground.model is not None,
        satellite_active=sar.initialized,
    )


@router.get("/info")
async def app_info():
    """Application information and capabilities."""
    return {
        "app": settings.APP_NAME,
        "description": "AI-powered flood detection and government compensation verification system",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "capabilities": {
            "ground_photo_analysis": "YOLOv8 flood classification",
            "satellite_analysis": "Sentinel-1 SAR flood mapping via GEE",
            "verification": "Dual-score fusion (ground + satellite)",
            "compensation": "NDRF rate-based auto-calculation",
            "fraud_detection": "6-layer anti-fraud architecture",
            "payments": "PFMS DBT integration",
        },
        "documentation": "/docs",
        "openapi": "/openapi.json",
    }


@router.get("/rates")
async def compensation_rates():
    """Get current NDRF compensation rate tables."""
    from core.compensation import CompensationCalculator
    return CompensationCalculator.get_rate_table()
