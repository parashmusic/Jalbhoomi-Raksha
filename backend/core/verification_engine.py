# backend/core/verification_engine.py — Score fusion + claim routing
"""
Orchestrates the dual verification pipeline:
  1. Ground photo analysis (via FloodGroundDetector)
  2. Satellite cross-validation (via SARFloodMapper)
  3. Fraud checks (via FraudDetector)
  4. Score fusion → claim status routing
  5. Compensation calculation

This is the central brain of BhumiRaksha.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from loguru import logger

from core.flood_detector import FloodGroundDetector, GroundAnalysisResult
from core.sar_processor import SARFloodMapper, SatelliteResult
from core.compensation import CompensationCalculator, CompensationBreakdown


class ClaimStatus(str, Enum):
    """Claim routing status based on verification score."""
    AUTO_APPROVED = "AUTO_APPROVED"           # Score ≥ 75
    OFFICER_REVIEW = "OFFICER_REVIEW"         # Score 55–74
    FIELD_VERIFICATION = "FIELD_VERIFICATION" # Score 35–54
    REJECTED = "REJECTED"                     # Score < 35
    FRAUD_FLAGGED = "FRAUD_FLAGGED"           # Fraud detected


# Score thresholds
THRESHOLD_AUTO_APPROVE = 75
THRESHOLD_OFFICER_REVIEW = 55
THRESHOLD_FIELD_VERIFY = 35


@dataclass
class VerificationResult:
    """Complete result of the dual verification pipeline."""
    claim_id: str
    total_score: int               # 0 – 100
    ground_score: int              # 0 – 50
    satellite_score: int           # 0 – 50
    status: ClaimStatus
    estimated_compensation: float  # INR
    flood_area_ha: float
    flood_percentage: float
    ndvi_loss: float
    satellite_confidence: str
    ground_confidence: float
    ground_damage_class: str
    ground_flood_detected: bool
    flags: List[str]
    sms_message: str
    compensation_breakdown: Optional[CompensationBreakdown] = None
    processed_at: datetime = field(default_factory=datetime.utcnow)


class VerificationEngine:
    """
    Central verification orchestrator.

    Flow:
      1. Analyze all ground photos → take best score
      2. Run satellite cross-validation
      3. Check for fraud signals
      4. Fuse scores → route claim
      5. Calculate compensation (if applicable)
      6. Build SMS notification
    """

    def __init__(
        self,
        ground_detector: FloodGroundDetector,
        sar_mapper: SARFloodMapper,
        compensation_calc: CompensationCalculator,
    ):
        self.ground = ground_detector
        self.sar = sar_mapper
        self.comp_calc = compensation_calc

    def process_claim(self, claim: Dict[str, Any]) -> VerificationResult:
        """
        Run the full verification pipeline on a submitted claim.

        Args:
            claim: Dict containing:
                - claim_id: str
                - photo_paths: List[str]
                - submitted_lat, submitted_lon: float
                - event_date: datetime or str
                - village_polygon: Shapely geometry
                - village_geojson: dict
                - claimed_area_ha: float
                - crop_type: str
                - state: str
                - house_damage_type: Optional[str]

        Returns:
            VerificationResult with scores, status, and compensation
        """
        claim_id = claim['claim_id']
        logger.info(f"━━━ Processing claim {claim_id} ━━━")

        # ── Step 1: Analyze ground photos ────────────────────────
        ground_results: List[GroundAnalysisResult] = []
        for photo_path in claim.get('photo_paths', []):
            try:
                r = self.ground.analyze(
                    photo_path,
                    claim['submitted_lat'],
                    claim['submitted_lon'],
                    claim['event_date'] if isinstance(claim['event_date'], datetime)
                        else datetime.strptime(str(claim['event_date']), '%Y-%m-%d'),
                    claim.get('village_polygon'),
                )
                ground_results.append(r)
                logger.info(f"  Photo {photo_path}: class={r.damage_class}, score={r.ground_score}")
            except Exception as e:
                logger.error(f"  Photo analysis failed for {photo_path}: {e}")

        # Fallback if no photos could be analyzed
        if not ground_results:
            logger.warning(f"  No photos analyzed for claim {claim_id}")
            ground_results.append(GroundAnalysisResult(
                flood_detected=False, confidence=0.0, ground_score=0,
                damage_class='no_damage', gps_valid=False,
                timestamp_valid=False, is_duplicate=False,
                flags=['NO_PHOTOS_ANALYZED'],
            ))

        # Take best ground score from multi-photo submission
        best_ground = max(ground_results, key=lambda x: x.ground_score)
        all_flags = list(set(f for r in ground_results for f in r.flags))

        logger.info(f"  Best ground score: {best_ground.ground_score}/50 ({best_ground.damage_class})")

        # ── Step 2: Fraud check override ─────────────────────────
        if 'DUPLICATE_IMAGE' in all_flags:
            logger.warning(f"  ⚠ FRAUD: Duplicate image detected for claim {claim_id}")
            return self._build_fraud_result(
                claim_id, all_flags,
                "⚠ Claim rejected: duplicate image detected. Ref: FRAUD-PHOTO"
            )

        # ── Step 3: Satellite cross-validation ───────────────────
        event_date_str = (
            claim['event_date'].strftime('%Y-%m-%d')
            if isinstance(claim['event_date'], datetime)
            else str(claim['event_date'])
        )

        sat_result = self.sar.analyze_village(
            village_geojson=claim.get('village_geojson', {'coordinates': []}),
            event_date=event_date_str,
            claimed_area_ha=claim.get('claimed_area_ha', 1.0),
        )

        logger.info(
            f"  Satellite: {sat_result.flooded_area_ha}ha flooded "
            f"({sat_result.flood_percentage}%), score={sat_result.satellite_score}/50"
        )

        # ── Step 4: Compute total score ──────────────────────────
        total = best_ground.ground_score + sat_result.satellite_score
        logger.info(f"  Total score: {total}/100 (ground={best_ground.ground_score} + sat={sat_result.satellite_score})")

        # ── Step 5: Route by score ───────────────────────────────
        if total >= THRESHOLD_AUTO_APPROVE:
            status = ClaimStatus.AUTO_APPROVED
        elif total >= THRESHOLD_OFFICER_REVIEW:
            status = ClaimStatus.OFFICER_REVIEW
        elif total >= THRESHOLD_FIELD_VERIFY:
            status = ClaimStatus.FIELD_VERIFICATION
        else:
            status = ClaimStatus.REJECTED

        logger.info(f"  Status: {status.value}")

        # ── Step 6: Calculate compensation ───────────────────────
        comp = None
        comp_amount = 0.0
        if status != ClaimStatus.REJECTED:
            comp = self.comp_calc.calculate(
                area_ha=sat_result.flooded_area_ha,
                crop_type=claim.get('crop_type', 'paddy_rainfed'),
                damage_pct=sat_result.flood_percentage / 100,
                state=claim.get('state', 'Assam'),
                house_damage_type=claim.get('house_damage_type'),
            )
            comp_amount = comp.total
            logger.info(f"  Compensation: ₹{comp_amount:,.0f}")

        # ── Step 7: Build SMS ────────────────────────────────────
        sms = self._build_sms(claim_id, total, status, comp_amount)

        return VerificationResult(
            claim_id=claim_id,
            total_score=total,
            ground_score=best_ground.ground_score,
            satellite_score=sat_result.satellite_score,
            status=status,
            estimated_compensation=comp_amount,
            flood_area_ha=sat_result.flooded_area_ha,
            flood_percentage=sat_result.flood_percentage,
            ndvi_loss=sat_result.ndvi_loss,
            satellite_confidence=sat_result.confidence,
            ground_confidence=best_ground.confidence,
            ground_damage_class=best_ground.damage_class,
            ground_flood_detected=best_ground.flood_detected,
            flags=all_flags,
            sms_message=sms,
            compensation_breakdown=comp,
        )

    def _build_fraud_result(self, claim_id: str, flags: List[str], message: str) -> VerificationResult:
        """Build a result for fraud-flagged claims (score = 0)."""
        return VerificationResult(
            claim_id=claim_id,
            total_score=0,
            ground_score=0,
            satellite_score=0,
            status=ClaimStatus.FRAUD_FLAGGED,
            estimated_compensation=0,
            flood_area_ha=0,
            flood_percentage=0,
            ndvi_loss=0,
            satellite_confidence='LOW',
            ground_confidence=0,
            ground_damage_class='no_damage',
            ground_flood_detected=False,
            flags=flags,
            sms_message=f"BhumiRaksha [{claim_id}]: {message}",
        )

    @staticmethod
    def _build_sms(cid: str, score: int, status: ClaimStatus, comp: float) -> str:
        """Build SMS notification for the Gaon Bura."""
        status_messages = {
            ClaimStatus.AUTO_APPROVED:
                f"✓ APPROVED. Payment ₹{comp:,.0f} in 48h.",
            ClaimStatus.OFFICER_REVIEW:
                "Under review by district officer (48h).",
            ClaimStatus.FIELD_VERIFICATION:
                "Field survey scheduled in 5 days.",
            ClaimStatus.REJECTED:
                "Insufficient evidence. Resubmit via portal.",
            ClaimStatus.FRAUD_FLAGGED:
                "⚠ Flagged for investigation.",
        }
        msg = status_messages.get(status, '')
        return f"BhumiRaksha [{cid}]: {msg} Score:{score}/100"
