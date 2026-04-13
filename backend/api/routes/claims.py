# backend/api/routes/claims.py — Claim submission & status endpoints
"""
API endpoints for the Gaon Bura mobile app:
  - Submit flood damage claims with geo-tagged photos
  - Check claim status
  - View verification details
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from loguru import logger

from models.schemas import ClaimStatusResponse
from api.dependencies import (
    get_verification_engine,
    get_fraud_detector,
)
from services.storage_service import storage_service
from services.sms_service import sms_service
from services.pfms_service import pfms_service
from core.verification_engine import VerificationEngine, ClaimStatus

router = APIRouter(prefix="/claims", tags=["Claims"])


@router.post("/submit", response_model=ClaimStatusResponse)
async def submit_claim(
    background_tasks: BackgroundTasks,
    photos: List[UploadFile] = File(..., description="Min 3 geo-tagged photos"),
    aadhaar_token: str = Form(..., description="Hashed Aadhaar (NOT raw)"),
    village_id: str = Form(..., description="Village code from Census DB"),
    crop_type: str = Form(..., description="paddy_rainfed, wheat, jute, etc."),
    claimed_area: float = Form(..., gt=0, description="Affected area in hectares"),
    event_date: str = Form(..., description="Flood event date (YYYY-MM-DD)"),
    submitted_lat: float = Form(..., ge=-90, le=90),
    submitted_lon: float = Form(..., ge=-180, le=180),
    damage_type: str = Form("crop", description="crop / house / both"),
    house_damage: Optional[str] = Form(None, description="pucca_full / kutcha_full etc."),
    state: str = Form("Assam"),
):
    """
    Submit a new flood damage claim.

    Requires minimum 3 geo-tagged photos captured on-site.
    Photos are validated for GPS, timestamp, and duplicates.
    The verification pipeline runs automatically:
      1. YOLOv8 ground photo analysis
      2. Sentinel-1 SAR satellite cross-validation
      3. Score fusion → auto-routing
      4. NDRF compensation calculation
    """
    # ── Validate minimum photos ──────────────────────────────────
    if len(photos) < 3:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum 3 photos required for claim submission. Received: {len(photos)}"
        )

    # ── Generate claim ID ────────────────────────────────────────
    claim_id = f"CLM-{uuid4().hex[:8].upper()}"
    logger.info(f"━━━ New claim: {claim_id} from village {village_id} ━━━")

    # ── Save photos ──────────────────────────────────────────────
    try:
        photo_paths = await storage_service.save_claim_photos(claim_id, photos)
        logger.info(f"  Saved {len(photo_paths)} photos")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Build claim object ───────────────────────────────────────
    claim = {
        'claim_id': claim_id,
        'photo_paths': photo_paths,
        'village_id': village_id,
        'crop_type': crop_type,
        'claimed_area_ha': claimed_area,
        'event_date': event_date,
        'submitted_lat': submitted_lat,
        'submitted_lon': submitted_lon,
        'village_geojson': {
            # In production, fetch from PostGIS by village_id
            'coordinates': [
                _generate_mock_polygon(submitted_lat, submitted_lon)
            ],
        },
        'village_polygon': None,  # Would be Shapely polygon from DB
        'state': state,
        'damage_type': damage_type,
        'house_damage_type': house_damage,
        'aadhaar_token': aadhaar_token,
    }

    # ── Run verification pipeline ────────────────────────────────
    engine = get_verification_engine()
    result = engine.process_claim(claim)

    logger.info(
        f"  Result: {result.status.value} | Score: {result.total_score}/100 | "
        f"Compensation: ₹{result.estimated_compensation:,.0f}"
    )

    # ── Send SMS notification (background) ───────────────────────
    background_tasks.add_task(
        _send_claim_sms,
        village_id=village_id,
        claim_id=claim_id,
        sms_message=result.sms_message,
    )

    # ── Queue payment if auto-approved ───────────────────────────
    if result.status == ClaimStatus.AUTO_APPROVED:
        background_tasks.add_task(
            _queue_payment,
            claim_id=claim_id,
            aadhaar_token=aadhaar_token,
            amount=result.estimated_compensation,
            state=state,
            district="Unknown",  # Would come from DB
        )

    return ClaimStatusResponse(
        claim_id=claim_id,
        status=result.status.value,
        total_score=result.total_score,
        estimated_compensation=result.estimated_compensation,
        flood_area_ha=result.flood_area_ha,
        message=result.sms_message,
    )


@router.get("/{claim_id}", response_model=ClaimStatusResponse)
async def get_claim_status(claim_id: str):
    """
    Check status of a submitted claim.
    Also accessible via SMS: "STATUS <ClaimID> to 14416"
    """
    # In production, fetch from database
    # For now, return a mock response
    logger.info(f"Status check: {claim_id}")

    # TODO: Fetch from DB
    # claim = await db_get_claim(claim_id)
    # if not claim:
    #     raise HTTPException(404, "Claim not found")

    return ClaimStatusResponse(
        claim_id=claim_id,
        status="PROCESSING",
        total_score=None,
        estimated_compensation=None,
        flood_area_ha=None,
        message=f"Claim {claim_id} is being processed. You will receive an SMS update.",
    )


@router.get("/{claim_id}/verification")
async def get_verification_details(claim_id: str):
    """Get detailed verification breakdown for a claim."""
    # TODO: Fetch from DB
    return {
        "claim_id": claim_id,
        "message": "Verification details will be available after processing",
        "hint": "In production, this returns full VerificationScoreResponse",
    }


# ── Helper functions ─────────────────────────────────────────────────

async def _send_claim_sms(village_id: str, claim_id: str, sms_message: str):
    """Background task: Send SMS notification."""
    # In production, fetch phone number from GaonBura record
    phone = "+919999999999"  # Placeholder
    await sms_service.send(phone, sms_message, claim_id)


async def _queue_payment(
    claim_id: str, aadhaar_token: str, amount: float,
    state: str, district: str,
):
    """Background task: Queue PFMS payment."""
    await pfms_service.queue_transfer(
        claim_id=claim_id,
        aadhaar_token=aadhaar_token,
        amount=amount,
        state=state,
        district=district,
    )


def _generate_mock_polygon(lat: float, lon: float, delta: float = 0.01):
    """Generate a mock square polygon around a point for development."""
    return [
        [lon - delta, lat - delta],
        [lon + delta, lat - delta],
        [lon + delta, lat + delta],
        [lon - delta, lat + delta],
        [lon - delta, lat - delta],
    ]
