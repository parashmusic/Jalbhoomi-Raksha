# backend/services/pfms_service.py — PFMS payment integration
"""
Integration with Public Financial Management System (PFMS) for
Direct Benefit Transfer (DBT) to farmer bank accounts.

In production, this connects to the PFMS API at pfms.nic.in
to trigger Aadhaar-linked bank transfers via NPCI.
"""

import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from config import settings


class PFMSService:
    """
    PFMS API integration for government compensation transfers.

    Flow:
      1. Claim approved → queue_transfer()
      2. Fetch Aadhaar-linked bank account via NPCI mapper
      3. Submit payment request to PFMS
      4. Track payment status
    """

    def __init__(self):
        self.api_url = settings.PFMS_API_URL
        self.api_key = settings.PFMS_API_KEY
        self.agency_code = settings.PFMS_AGENCY_CODE

    async def queue_transfer(
        self,
        claim_id: str,
        aadhaar_token: str,
        amount: float,
        state: str,
        district: str,
        scheme_code: str = "SDRF",
    ) -> Dict[str, Any]:
        """
        Queue a DBT transfer for an approved claim.

        Args:
            claim_id: BhumiRaksha claim ID
            aadhaar_token: Hashed Aadhaar for beneficiary lookup
            amount: Compensation amount in INR
            state: State name
            district: District name
            scheme_code: SDRF / NDRF scheme head

        Returns:
            Dict with transaction reference and status
        """
        logger.info(
            f"Queueing PFMS transfer: ₹{amount:,.0f} for claim {claim_id} "
            f"({district}, {state})"
        )

        if settings.APP_ENV == "development":
            return self._mock_transfer(claim_id, amount)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/dbt/initiate",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "X-Agency-Code": self.agency_code,
                        "Content-Type": "application/json",
                    },
                    json={
                        "beneficiary_aadhaar_hash": aadhaar_token,
                        "amount": amount,
                        "scheme_code": scheme_code,
                        "state": state,
                        "district": district,
                        "reference_id": claim_id,
                        "narration": f"BhumiRaksha Flood Relief - {claim_id}",
                        "head_of_account": f"2245-SDRF-{state[:3].upper()}",
                    },
                    timeout=30.0,
                )

                data = response.json()

                if response.status_code == 200:
                    return {
                        "success": True,
                        "transaction_id": data.get("transaction_id"),
                        "status": "QUEUED",
                        "estimated_credit": "24-48 hours",
                    }
                else:
                    logger.error(f"PFMS API error: {data}")
                    return {
                        "success": False,
                        "error": data.get("message", "Unknown error"),
                    }
        except Exception as e:
            logger.error(f"PFMS transfer failed: {e}")
            return {"success": False, "error": str(e)}

    async def check_status(self, transaction_id: str) -> Dict[str, Any]:
        """Check payment status from PFMS."""
        if settings.APP_ENV == "development":
            return {
                "transaction_id": transaction_id,
                "status": "CREDITED",
                "credited_at": datetime.utcnow().isoformat(),
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/dbt/status/{transaction_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10.0,
                )
                return response.json()
        except Exception as e:
            logger.error(f"PFMS status check failed: {e}")
            return {"error": str(e)}

    async def bulk_transfer(
        self,
        transfers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Process multiple transfers in batch.

        Args:
            transfers: List of dicts with claim_id, aadhaar_token, amount, etc.

        Returns:
            Summary of batch processing results
        """
        results = []
        total_success = 0
        total_amount = 0

        for transfer in transfers:
            result = await self.queue_transfer(
                claim_id=transfer['claim_id'],
                aadhaar_token=transfer['aadhaar_token'],
                amount=transfer['amount'],
                state=transfer.get('state', 'Assam'),
                district=transfer.get('district', 'Unknown'),
            )
            results.append(result)
            if result.get('success'):
                total_success += 1
                total_amount += transfer['amount']

        return {
            "total_submitted": len(transfers),
            "successful": total_success,
            "failed": len(transfers) - total_success,
            "total_amount": total_amount,
            "results": results,
        }

    def _mock_transfer(self, claim_id: str, amount: float) -> Dict[str, Any]:
        """Mock transfer for development."""
        import hashlib
        txn_id = f"TXN-{hashlib.md5(claim_id.encode()).hexdigest()[:12].upper()}"
        logger.info(f"[MOCK PFMS] Transfer ₹{amount:,.0f} → {txn_id}")
        return {
            "success": True,
            "transaction_id": txn_id,
            "status": "QUEUED",
            "estimated_credit": "24-48 hours (mock)",
        }


# Singleton
pfms_service = PFMSService()
