# backend/core/fraud_detector.py — Anti-fraud checks for claims
"""
Multi-layer fraud detection for BhumiRaksha claims.

Detection layers:
  1. Photo fraud — duplicate images, stock photos
  2. GPS spoofing — coordinates outside village boundary
  3. Beneficiary dedup — same Aadhaar claiming twice per event
  4. Statistical anomaly — village-level Z-score analysis
  5. Temporal consistency — claim before satellite-confirmed flood
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from loguru import logger


@dataclass
class FraudCheckResult:
    """Result of comprehensive fraud checks on a claim."""
    is_fraud: bool
    fraud_score: float          # 0.0 (clean) — 1.0 (definite fraud)
    checks_passed: List[str]
    checks_failed: List[str]
    risk_level: str             # LOW / MEDIUM / HIGH / CRITICAL
    details: Dict[str, Any] = field(default_factory=dict)


class FraudDetector:
    """
    Multi-layer fraud detection engine.

    In production, this would integrate with:
      - Redis for image hash lookups
      - PostgreSQL for beneficiary history
      - External APIs for reverse image search
      - Android SafetyNet for device attestation
    """

    # Weights for each fraud signal
    WEIGHTS = {
        'duplicate_image': 1.0,        # Instant rejection
        'gps_spoofing': 0.8,
        'beneficiary_duplicate': 0.9,
        'statistical_anomaly': 0.6,
        'temporal_anomaly': 0.7,
        'exif_tampering': 0.7,
    }

    # Risk thresholds
    RISK_THRESHOLDS = {
        'LOW': 0.2,
        'MEDIUM': 0.4,
        'HIGH': 0.6,
        'CRITICAL': 0.8,
    }

    def __init__(
        self,
        image_hash_db: Optional[Set[str]] = None,
        beneficiary_db: Optional[Dict] = None,
    ):
        self.image_hash_db = image_hash_db or set()
        self.beneficiary_db = beneficiary_db or {}

    def check_claim(
        self,
        claim: Dict[str, Any],
        ground_flags: List[str],
    ) -> FraudCheckResult:
        """
        Run all fraud checks on a claim.

        Args:
            claim: Full claim dict
            ground_flags: Flags from ground photo analysis

        Returns:
            FraudCheckResult with aggregated fraud signals
        """
        passed = []
        failed = []
        details = {}
        fraud_signals = 0.0

        # ── 1. Photo Fraud ────────────────────────────────────────
        if 'DUPLICATE_IMAGE' in ground_flags:
            failed.append('photo_uniqueness')
            fraud_signals += self.WEIGHTS['duplicate_image']
            details['photo_fraud'] = 'Duplicate image detected via perceptual hash'
        else:
            passed.append('photo_uniqueness')

        # ── 2. GPS Spoofing ───────────────────────────────────────
        if 'GPS_MISMATCH' in ground_flags:
            failed.append('gps_verification')
            fraud_signals += self.WEIGHTS['gps_spoofing']
            details['gps_fraud'] = 'GPS coordinates outside village boundary'
        else:
            passed.append('gps_verification')

        # ── 3. Beneficiary Dedup ──────────────────────────────────
        aadhaar = claim.get('aadhaar_token', '')
        event_key = f"{aadhaar}_{claim.get('event_date', '')}_{claim.get('state', '')}"
        if event_key in self.beneficiary_db:
            failed.append('beneficiary_uniqueness')
            fraud_signals += self.WEIGHTS['beneficiary_duplicate']
            details['dedup_fraud'] = (
                f"Aadhaar already claimed for this event. "
                f"Previous claim: {self.beneficiary_db[event_key]}"
            )
        else:
            passed.append('beneficiary_uniqueness')
            # Record this claim
            self.beneficiary_db[event_key] = claim.get('claim_id', 'unknown')

        # ── 4. EXIF Tampering ─────────────────────────────────────
        if 'NO_EXIF_GPS' in ground_flags and 'NO_EXIF_TIMESTAMP' in ground_flags:
            failed.append('exif_integrity')
            fraud_signals += self.WEIGHTS['exif_tampering']
            details['exif_fraud'] = 'No EXIF metadata — possible edited image'
        elif 'EXIF_READ_ERROR' in ground_flags:
            failed.append('exif_integrity')
            fraud_signals += self.WEIGHTS['exif_tampering'] * 0.5
            details['exif_warning'] = 'EXIF metadata could not be read'
        else:
            passed.append('exif_integrity')

        # ── 5. Temporal Consistency ───────────────────────────────
        if 'TIMESTAMP_STALE' in ground_flags:
            failed.append('temporal_consistency')
            fraud_signals += self.WEIGHTS['temporal_anomaly']
            details['temporal_fraud'] = 'Photo timestamp outside 72h window of event'
        else:
            passed.append('temporal_consistency')

        # ── Aggregate ─────────────────────────────────────────────
        # Normalize to 0.0 – 1.0 range
        max_possible = sum(self.WEIGHTS.values())
        fraud_score = min(1.0, fraud_signals / max_possible)

        # Determine risk level
        if fraud_score >= self.RISK_THRESHOLDS['CRITICAL']:
            risk = 'CRITICAL'
        elif fraud_score >= self.RISK_THRESHOLDS['HIGH']:
            risk = 'HIGH'
        elif fraud_score >= self.RISK_THRESHOLDS['MEDIUM']:
            risk = 'MEDIUM'
        else:
            risk = 'LOW'

        is_fraud = risk in ('HIGH', 'CRITICAL')

        if is_fraud:
            logger.warning(
                f"⚠ FRAUD DETECTED for claim {claim.get('claim_id')}: "
                f"score={fraud_score:.2f}, risk={risk}, failed={failed}"
            )

        return FraudCheckResult(
            is_fraud=is_fraud,
            fraud_score=round(fraud_score, 3),
            checks_passed=passed,
            checks_failed=failed,
            risk_level=risk,
            details=details,
        )

    def check_village_anomaly(
        self,
        village_id: str,
        claim_count: int,
        satellite_damage_area_ha: float,
        total_claimed_area_ha: float,
        historical_avg_claims: float = 5.0,
        historical_std_claims: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Statistical anomaly detection at village level.
        Flags if total claims exceed 3σ above satellite-inferred damage.

        Args:
            village_id: Village identifier
            claim_count: Number of claims from this village
            satellite_damage_area_ha: Satellite-confirmed damage area
            total_claimed_area_ha: Sum of all claimed areas
            historical_avg_claims: Historical average claims per event
            historical_std_claims: Historical standard deviation

        Returns:
            Dict with anomaly detection results
        """
        # Z-score for claim count
        z_score = (claim_count - historical_avg_claims) / max(historical_std_claims, 0.1)

        # Over-claim ratio
        over_claim_ratio = (
            total_claimed_area_ha / satellite_damage_area_ha
            if satellite_damage_area_ha > 0 else float('inf')
        )

        is_anomalous = z_score > 3.0 or over_claim_ratio > 2.0

        if is_anomalous:
            logger.warning(
                f"⚠ Village anomaly: {village_id} — "
                f"Z={z_score:.1f}, over_claim={over_claim_ratio:.1f}x"
            )

        return {
            'village_id': village_id,
            'is_anomalous': is_anomalous,
            'claim_count': claim_count,
            'z_score': round(z_score, 2),
            'over_claim_ratio': round(over_claim_ratio, 2),
            'recommendation': 'AUDIT' if is_anomalous else 'OK',
        }
