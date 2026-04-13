# backend/api/dependencies.py — Shared dependencies for API routes
"""
FastAPI dependency injection for authentication, database sessions,
and core service instances.
"""

from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from jose import jwt, JWTError
from datetime import datetime, timedelta
from passlib.context import CryptContext
from loguru import logger

from config import settings
from database import get_db, AsyncSession
from core.flood_detector import FloodGroundDetector
from core.sar_processor import SARFloodMapper
from core.compensation import CompensationCalculator
from core.verification_engine import VerificationEngine
from core.fraud_detector import FraudDetector

# ── Password hashing ─────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT Token Management ─────────────────────────────────────────────
security = HTTPBearer(auto_error=False)

def create_officer_token(data: dict) -> str:
    """Create JWT token for officer authentication."""
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(hours=settings.OFFICER_JWT_EXPIRY_HOURS)
    payload.update({"exp": expire, "type": "officer"})
    return jwt.encode(payload, settings.OFFICER_JWT_SECRET, algorithm="HS256")

def decode_officer_token(token: str) -> dict:
    """Decode and validate officer JWT token."""
    try:
        payload = jwt.decode(token, settings.OFFICER_JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "officer":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ── Auth Dependencies ─────────────────────────────────────────────────

async def get_current_officer(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Dependency: Extract and validate officer from JWT token."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return decode_officer_token(credentials.credentials)


async def verify_gaon_bura_token(
    aadhaar_token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify Gaon Bura's hashed Aadhaar token.
    In production, this would validate against UIDAI API response.
    """
    # For development, accept any non-empty token
    if not aadhaar_token:
        raise HTTPException(status_code=401, detail="Aadhaar token required")
    return {"aadhaar_hash": aadhaar_token, "verified": True}


# ── Core Service Singletons ──────────────────────────────────────────
# These are initialized once and reused across requests

_ground_detector: Optional[FloodGroundDetector] = None
_sar_mapper: Optional[SARFloodMapper] = None
_compensation_calc: Optional[CompensationCalculator] = None
_verification_engine: Optional[VerificationEngine] = None
_fraud_detector: Optional[FraudDetector] = None


def get_ground_detector() -> FloodGroundDetector:
    """Get or create the flood ground detector."""
    global _ground_detector
    if _ground_detector is None:
        _ground_detector = FloodGroundDetector(
            model_path=settings.YOLO_MODEL_PATH,
        )
    return _ground_detector


def get_sar_mapper() -> SARFloodMapper:
    """Get or create the SAR flood mapper."""
    global _sar_mapper
    if _sar_mapper is None:
        _sar_mapper = SARFloodMapper(
            project=settings.GEE_PROJECT,
            service_account=settings.GEE_SERVICE_ACCOUNT,
            key_file=settings.GEE_KEY_FILE,
        )
    return _sar_mapper


def get_compensation_calc() -> CompensationCalculator:
    """Get or create the compensation calculator."""
    global _compensation_calc
    if _compensation_calc is None:
        _compensation_calc = CompensationCalculator()
    return _compensation_calc


def get_fraud_detector() -> FraudDetector:
    """Get or create the fraud detector."""
    global _fraud_detector
    if _fraud_detector is None:
        _fraud_detector = FraudDetector()
    return _fraud_detector


def get_verification_engine() -> VerificationEngine:
    """Get or create the verification engine."""
    global _verification_engine
    if _verification_engine is None:
        _verification_engine = VerificationEngine(
            ground_detector=get_ground_detector(),
            sar_mapper=get_sar_mapper(),
            compensation_calc=get_compensation_calc(),
        )
    return _verification_engine
