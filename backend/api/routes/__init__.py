# backend/api/routes/__init__.py
from api.routes.health import router as health_router
from api.routes.claims import router as claims_router
from api.routes.officer import router as officer_router

__all__ = ["health_router", "claims_router", "officer_router"]
