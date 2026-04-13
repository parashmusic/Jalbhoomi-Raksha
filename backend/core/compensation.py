# backend/core/compensation.py — NDRF rate-based compensation calculator
"""
Calculates flood damage compensation based on NDRF (National Disaster
Response Fund) norms. Supports crop loss, house damage, and state-specific
multipliers.

Formula: hectares × crop_rate × damage% × state_multiplier
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from loguru import logger


# ── NDRF Norms (2023 revision) — INR per hectare ─────────────────────

CROP_RATES: Dict[str, float] = {
    'paddy_rainfed': 6800,
    'paddy_irrigated': 13500,
    'wheat': 6800,
    'jute': 6800,
    'sugarcane': 18000,
    'vegetables': 13500,
    'perennial_crops': 18000,
}

HOUSE_RATES: Dict[str, float] = {
    'pucca_full': 95100,
    'pucca_partial': 5200,
    'kutcha_full': 3200,
    'kutcha_partial': 3200,
}

# State-specific multipliers (Assam, Bihar get higher due to frequency)
STATE_MULTIPLIERS: Dict[str, float] = {
    'Assam': 1.2,
    'Bihar': 1.15,
    'Odisha': 1.1,
    'Uttar Pradesh': 1.0,
    'West Bengal': 1.05,
    'Jharkhand': 1.0,
    'Meghalaya': 1.15,
    'Manipur': 1.1,
    'Nagaland': 1.1,
    'Tripura': 1.05,
    'Arunachal Pradesh': 1.1,
    'Andhra Pradesh': 1.0,
    'Telangana': 1.0,
    'Karnataka': 1.0,
    'Kerala': 1.05,
    'Tamil Nadu': 1.0,
    'Maharashtra': 1.0,
    'Gujarat': 1.0,
    'Rajasthan': 1.0,
    'Madhya Pradesh': 1.0,
    'Chhattisgarh': 1.0,
    'Punjab': 1.0,
    'Haryana': 1.0,
    'Uttarakhand': 1.05,
    'Himachal Pradesh': 1.05,
}

# Maximum compensation caps per beneficiary per event
MAX_CROP_COMPENSATION = 500000     # ₹5,00,000
MAX_HOUSE_COMPENSATION = 195100    # ₹1,95,100
MAX_TOTAL_COMPENSATION = 695100    # ₹6,95,100


@dataclass
class CompensationBreakdown:
    """Detailed compensation breakdown."""
    crop_loss: float
    house_damage: float
    total: float
    breakdown_str: str
    crop_type: str = ""
    area_ha: float = 0.0
    damage_pct: float = 0.0
    state: str = ""
    state_multiplier: float = 1.0
    rate_per_ha: float = 0.0
    capped: bool = False


class CompensationCalculator:
    """
    NDRF rate-based compensation calculator.

    Computes compensation for:
      - Crop loss: area × NDRF rate × damage% × state multiplier
      - House damage: fixed rates based on house type and damage severity
    """

    def calculate(
        self,
        area_ha: float,
        crop_type: str,
        damage_pct: float,           # 0.0 – 1.0
        state: str,
        house_damage_type: Optional[str] = None,
    ) -> CompensationBreakdown:
        """
        Calculate compensation for a single claim.

        Args:
            area_ha: Flooded area in hectares (from SAR analysis)
            crop_type: Type of crop (maps to NDRF rate table)
            damage_pct: Fraction of area damaged (0.0-1.0)
            state: State name (for multiplier lookup)
            house_damage_type: Optional house damage category

        Returns:
            CompensationBreakdown with itemized amounts
        """
        multiplier = STATE_MULTIPLIERS.get(state, 1.0)
        rate = CROP_RATES.get(crop_type, 6800)

        # Crop loss: area × rate × damage% × state multiplier
        crop_loss = area_ha * rate * damage_pct * multiplier
        crop_loss = min(crop_loss, MAX_CROP_COMPENSATION)  # Cap

        # House damage (if reported)
        house_loss = 0.0
        if house_damage_type:
            house_loss = HOUSE_RATES.get(house_damage_type, 0)
            house_loss = min(house_loss, MAX_HOUSE_COMPENSATION)

        total = crop_loss + house_loss
        capped = total >= MAX_TOTAL_COMPENSATION
        total = min(total, MAX_TOTAL_COMPENSATION)

        breakdown = (
            f"Crop: {area_ha:.1f}ha × ₹{rate:,} × {damage_pct*100:.0f}% × {multiplier} = ₹{crop_loss:,.0f}\n"
            f"House: ₹{house_loss:,.0f}\n"
            f"Total: ₹{total:,.0f}"
            + (" [CAPPED]" if capped else "")
        )

        logger.info(f"Compensation calculated: ₹{total:,.0f} for {area_ha}ha {crop_type} in {state}")

        return CompensationBreakdown(
            crop_loss=round(crop_loss, 2),
            house_damage=round(house_loss, 2),
            total=round(total, 2),
            breakdown_str=breakdown,
            crop_type=crop_type,
            area_ha=area_ha,
            damage_pct=damage_pct,
            state=state,
            state_multiplier=multiplier,
            rate_per_ha=rate,
            capped=capped,
        )

    def bulk_calculate(self, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a list of approved claims and return summary.

        Args:
            claims: List of dicts with keys: flooded_ha, crop_type,
                    damage_pct, state, district, claim_id

        Returns:
            Dict with individual_amounts, district_totals, and total_outgo
        """
        results = []
        district_totals = {}

        for claim in claims:
            comp = self.calculate(
                area_ha=claim.get('flooded_ha', 0),
                crop_type=claim.get('crop_type', 'paddy_rainfed'),
                damage_pct=claim.get('damage_pct', 0),
                state=claim.get('state', 'Assam'),
                house_damage_type=claim.get('house_damage_type'),
            )
            results.append(comp.total)

            district = claim.get('district', 'Unknown')
            if district not in district_totals:
                district_totals[district] = {'count': 0, 'total': 0}
            district_totals[district]['count'] += 1
            district_totals[district]['total'] += comp.total

        return {
            'individual_amounts': results,
            'district_totals': district_totals,
            'total_outgo': sum(results),
            'claim_count': len(results),
        }

    @staticmethod
    def get_rate_table() -> Dict[str, Any]:
        """Return the complete rate tables for reference."""
        return {
            'crop_rates': CROP_RATES,
            'house_rates': HOUSE_RATES,
            'state_multipliers': STATE_MULTIPLIERS,
            'caps': {
                'max_crop': MAX_CROP_COMPENSATION,
                'max_house': MAX_HOUSE_COMPENSATION,
                'max_total': MAX_TOTAL_COMPENSATION,
            },
        }
