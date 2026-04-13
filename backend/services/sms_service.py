# backend/services/sms_service.py — SMS notification service
"""
Sends SMS notifications to Gaon Buras and farmers.
Supports MSG91 (India) and Twilio as providers.
"""

import httpx
from typing import Optional
from loguru import logger
from config import settings


class SMSService:
    """SMS notification service with provider abstraction."""

    def __init__(self):
        self.provider = settings.SMS_PROVIDER

    async def send(
        self,
        phone: str,
        message: str,
        claim_id: Optional[str] = None,
    ) -> dict:
        """
        Send SMS to a phone number.

        Args:
            phone: Phone number (with country code)
            message: SMS text content
            claim_id: Optional claim reference for logging

        Returns:
            Dict with success status and message_id
        """
        logger.info(f"SMS → {phone}: {message[:50]}... (claim: {claim_id})")

        if settings.APP_ENV == "development":
            return self._mock_send(phone, message, claim_id)

        if self.provider == "msg91":
            return await self._send_msg91(phone, message)
        elif self.provider == "twilio":
            return await self._send_twilio(phone, message)
        else:
            logger.warning(f"Unknown SMS provider: {self.provider}")
            return {"success": False, "error": f"Unknown provider: {self.provider}"}

    async def _send_msg91(self, phone: str, message: str) -> dict:
        """Send via MSG91 API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://control.msg91.com/api/v5/flow/",
                    headers={
                        "authkey": settings.MSG91_AUTH_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "template_id": settings.MSG91_TEMPLATE_ID,
                        "sender": settings.MSG91_SENDER_ID,
                        "short_url": "0",
                        "mobiles": phone,
                        "message": message,
                    },
                    timeout=10.0,
                )
                data = response.json()
                return {
                    "success": response.status_code == 200,
                    "message_id": data.get("request_id"),
                    "error": data.get("message") if response.status_code != 200 else None,
                }
        except Exception as e:
            logger.error(f"MSG91 send failed: {e}")
            return {"success": False, "error": str(e)}

    async def _send_twilio(self, phone: str, message: str) -> dict:
        """Send via Twilio API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json",
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                    data={
                        "To": phone,
                        "From": settings.TWILIO_FROM_NUMBER,
                        "Body": message,
                    },
                    timeout=10.0,
                )
                data = response.json()
                return {
                    "success": response.status_code == 201,
                    "message_id": data.get("sid"),
                    "error": data.get("message") if response.status_code != 201 else None,
                }
        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            return {"success": False, "error": str(e)}

    def _mock_send(self, phone: str, message: str, claim_id: Optional[str]) -> dict:
        """Mock SMS for development — just logs it."""
        logger.info(f"[MOCK SMS] To: {phone} | Claim: {claim_id}\n  Message: {message}")
        return {
            "success": True,
            "message_id": f"mock_{claim_id or 'none'}",
            "error": None,
        }


# Singleton
sms_service = SMSService()
