# backend/api/routes/officer.py — District officer dashboard endpoints
"""
API endpoints for the district officer web dashboard:
  - Login with employee credentials
  - View pending claims for their district
  - Approve/reject individual or bulk claims
  - View district statistics
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime
from loguru import logger

from models.schemas import (
    OfficerLoginRequest,
    OfficerTokenResponse,
    BulkApproveRequest,
    BulkApproveResponse,
    PendingClaimSummary,
    PendingClaimsResponse,
)
from api.dependencies import (
    get_current_officer,
    create_officer_token,
    hash_password,
    verify_password,
    get_compensation_calc,
)
from services.pfms_service import pfms_service

router = APIRouter(prefix="/officer", tags=["Officer Dashboard"])


@router.post("/login", response_model=OfficerTokenResponse)
async def officer_login(request: OfficerLoginRequest):
    """
    Authenticate district officer with employee ID and password.
    Returns JWT token for subsequent API calls.
    """
    # TODO: In production, validate against Officer table in DB
    # For development, accept test credentials
    test_officers = {
        "OFF-001": {
            "password_hash": hash_password("admin123"),
            "name": "Rajesh Kumar",
            "district": "Kamrup",
            "state": "Assam",
        },
        "OFF-002": {
            "password_hash": hash_password("admin123"),
            "name": "Priya Singh",
            "district": "Patna",
            "state": "Bihar",
        },
    }

    officer = test_officers.get(request.employee_id)
    if not officer:
        raise HTTPException(status_code=401, detail="Invalid employee ID")

    # In dev, accept "admin123" as universal password
    if request.password != "admin123":
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_officer_token({
        "sub": request.employee_id,
        "name": officer["name"],
        "district": officer["district"],
        "state": officer["state"],
    })

    from config import settings
    return OfficerTokenResponse(
        access_token=token,
        officer_name=officer["name"],
        district=officer["district"],
        expires_in=settings.OFFICER_JWT_EXPIRY_HOURS * 3600,
    )


@router.get("/pending", response_model=PendingClaimsResponse)
async def get_pending_claims(
    officer: dict = Depends(get_current_officer),
):
    """
    Get all pending claims for the officer's district.
    Claims are sorted by score (highest first) for efficient review.
    """
    district = officer.get("district", "Unknown")
    logger.info(f"Officer {officer.get('name')} fetching pending claims for {district}")

    # TODO: Fetch from database
    # For development, return mock data
    mock_claims = [
        PendingClaimSummary(
            claim_id="CLM-A1B2C3D4",
            village_name="Nalbari Gaon",
            gaon_bura_name="Hari Kalita",
            damage_type="crop",
            claimed_area_ha=2.5,
            total_score=68,
            estimated_compensation=19584.0,
            fraud_flags=[],
            submitted_at=datetime(2026, 4, 10, 14, 30),
        ),
        PendingClaimSummary(
            claim_id="CLM-E5F6G7H8",
            village_name="Barpeta Road",
            gaon_bura_name="Mohan Das",
            damage_type="both",
            claimed_area_ha=3.8,
            total_score=72,
            estimated_compensation=35240.0,
            fraud_flags=[],
            submitted_at=datetime(2026, 4, 10, 16, 15),
        ),
        PendingClaimSummary(
            claim_id="CLM-I9J0K1L2",
            village_name="Dhubri Town",
            gaon_bura_name="Abdul Rahman",
            damage_type="crop",
            claimed_area_ha=1.2,
            total_score=42,
            estimated_compensation=0,
            fraud_flags=["GPS_MISMATCH"],
            submitted_at=datetime(2026, 4, 11, 9, 0),
        ),
    ]

    total_comp = sum(c.estimated_compensation or 0 for c in mock_claims)

    return PendingClaimsResponse(
        district=district,
        total_pending=len(mock_claims),
        total_estimated_compensation=total_comp,
        claims=mock_claims,
    )


@router.post("/approve", response_model=BulkApproveResponse)
async def bulk_approve(
    request: BulkApproveRequest,
    officer: dict = Depends(get_current_officer),
):
    """
    Bulk approve high-confidence claims.
    Triggers PFMS DBT transfer for each approved claim.
    """
    logger.info(
        f"Officer {officer.get('name')} bulk-approving "
        f"{len(request.claim_ids)} claims"
    )

    # TODO: In production:
    # 1. Validate all claim_ids exist and are in OFFICER_REVIEW status
    # 2. Update status to APPROVED
    # 3. Record audit log with officer ID
    # 4. Queue PFMS transfers

    # Mock: queue transfers
    total_compensation = 0.0
    for cid in request.claim_ids:
        result = await pfms_service.queue_transfer(
            claim_id=cid,
            aadhaar_token="mock_aadhaar",
            amount=15000.0,  # Would come from DB
            state=officer.get("state", "Assam"),
            district=officer.get("district", "Unknown"),
        )
        if result.get("success"):
            total_compensation += 15000.0

    return BulkApproveResponse(
        approved=len(request.claim_ids),
        queued_for_dbt=True,
        total_compensation=total_compensation,
        claim_ids=request.claim_ids,
    )


@router.post("/reject/{claim_id}")
async def reject_claim(
    claim_id: str,
    reason: str = "Insufficient evidence",
    officer: dict = Depends(get_current_officer),
):
    """
    Reject a claim with a reason code.
    SMS notification sent to Gaon Bura with rejection details.
    """
    logger.info(f"Officer {officer.get('name')} rejecting {claim_id}: {reason}")

    # TODO: Update DB, send SMS, log audit trail
    return {
        "claim_id": claim_id,
        "status": "REJECTED",
        "rejected_by": officer.get("name"),
        "reason": reason,
        "sms_sent": True,
    }


@router.get("/stats")
async def district_stats(
    officer: dict = Depends(get_current_officer),
):
    """
    Get district-level statistics for the officer's dashboard.
    """
    district = officer.get("district", "Unknown")

    # TODO: Aggregate from database
    return {
        "district": district,
        "state": officer.get("state", "Unknown"),
        "period": "Monsoon 2026",
        "summary": {
            "total_claims": 156,
            "auto_approved": 78,
            "officer_reviewed": 34,
            "field_verified": 22,
            "rejected": 12,
            "fraud_flagged": 10,
        },
        "financial": {
            "total_disbursed": 2845000,
            "pending_disbursement": 512000,
            "average_per_claim": 18237,
        },
        "coverage": {
            "villages_affected": 42,
            "total_villages": 180,
            "gaon_buras_active": 38,
            "total_area_ha": 1580,
        },
    }
