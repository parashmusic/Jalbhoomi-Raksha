# backend/models/schemas.py — Pydantic request/response schemas
"""
API schemas for request validation and response serialization.
Separate from ORM models to maintain clean API contracts.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime, date
from enum import Enum


# ── Enums (API-facing) ───────────────────────────────────────────────

class ClaimStatusAPI(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AUTO_APPROVED = "AUTO_APPROVED"
    OFFICER_REVIEW = "OFFICER_REVIEW"
    FIELD_VERIFICATION = "FIELD_VERIFICATION"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FRAUD_FLAGGED = "FRAUD_FLAGGED"
    PAYMENT_QUEUED = "PAYMENT_QUEUED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"


# ── Health ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "healthy"
    app_name: str = "BhumiRaksha"
    version: str = "1.0.0"
    database: str = "connected"
    redis: str = "connected"
    models_loaded: bool = False
    satellite_active: bool = False


# ── Claims ────────────────────────────────────────────────────────────

class ClaimSubmitRequest(BaseModel):
    """For documentation — actual submission uses multipart/form-data"""
    aadhaar_token: str = Field(..., description="Hashed Aadhaar, NOT raw number")
    village_id: str = Field(..., description="Village code from Census DB")
    crop_type: str = Field(..., description="Crop type: paddy_rainfed, wheat, etc.")
    claimed_area: float = Field(..., gt=0, description="Claimed affected area in hectares")
    event_date: str = Field(..., description="Flood event date (YYYY-MM-DD)")
    submitted_lat: float = Field(..., ge=-90, le=90, description="GPS latitude")
    submitted_lon: float = Field(..., ge=-180, le=180, description="GPS longitude")
    damage_type: str = Field("crop", description="crop / house / both / livestock")
    house_damage: Optional[str] = Field(None, description="pucca_full / pucca_partial / kutcha_full / kutcha_partial")
    state: str = Field("Assam", description="State name")


class ClaimStatusResponse(BaseModel):
    """Response after submitting a claim."""
    claim_id: str
    status: str
    total_score: Optional[int] = None
    estimated_compensation: Optional[float] = None
    flood_area_ha: Optional[float] = None
    message: str

    class Config:
        from_attributes = True


class VerificationScoreResponse(BaseModel):
    """Detailed verification breakdown."""
    ground_score: int = Field(ge=0, le=50)
    satellite_score: int = Field(ge=0, le=50)
    total_score: int = Field(ge=0, le=100)
    ground_flood_detected: bool
    ground_damage_class: str
    ground_confidence: float
    satellite_confidence: str
    flooded_area_ha: float
    flood_percentage: float
    ndvi_loss: float
    fraud_flags: List[str]


class CompensationBreakdownResponse(BaseModel):
    """Compensation calculation details."""
    crop_loss: float
    house_damage: float
    total: float
    breakdown_str: str
    crop_type: str
    area_ha: float
    damage_pct: float
    state: str
    state_multiplier: float


class ClaimDetailResponse(BaseModel):
    """Full claim details for officer dashboard."""
    claim_id: str
    village_name: str
    district: str
    state: str
    gaon_bura_name: str

    damage_type: str
    crop_type: Optional[str]
    claimed_area_ha: float
    event_date: date

    status: str
    total_score: Optional[int]
    ground_score: Optional[int]
    satellite_score: Optional[int]
    fraud_flags: List[str] = []

    estimated_compensation: Optional[float]
    flooded_area_ha: Optional[float]
    flood_percentage: Optional[float]

    photos_count: int = 0
    submitted_at: datetime
    verified_at: Optional[datetime] = None

    verification: Optional[VerificationScoreResponse] = None
    compensation: Optional[CompensationBreakdownResponse] = None

    class Config:
        from_attributes = True


# ── Officer ───────────────────────────────────────────────────────────

class OfficerLoginRequest(BaseModel):
    employee_id: str
    password: str


class OfficerTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    officer_name: str
    district: str
    expires_in: int  # seconds


class BulkApproveRequest(BaseModel):
    claim_ids: List[str] = Field(..., min_length=1, max_length=100)


class BulkApproveResponse(BaseModel):
    approved: int
    queued_for_dbt: bool
    total_compensation: float
    claim_ids: List[str]


class PendingClaimSummary(BaseModel):
    """Summary for officer's pending claims list."""
    claim_id: str
    village_name: str
    gaon_bura_name: str
    damage_type: str
    claimed_area_ha: float
    total_score: Optional[int]
    estimated_compensation: Optional[float]
    fraud_flags: List[str] = []
    submitted_at: datetime

    class Config:
        from_attributes = True


class PendingClaimsResponse(BaseModel):
    district: str
    total_pending: int
    total_estimated_compensation: float
    claims: List[PendingClaimSummary]


# ── SMS / Notifications ──────────────────────────────────────────────

class SMSRequest(BaseModel):
    phone: str
    message: str
    claim_id: Optional[str] = None


class SMSResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
