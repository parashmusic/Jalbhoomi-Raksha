# backend/services/storage_service.py — File storage for claim photos
"""
Handles file uploads (claim photos) with validation.
Stores files locally in development, can be extended for S3/GCS in production.
"""

import aiofiles
import hashlib
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from loguru import logger
from config import settings

from fastapi import UploadFile


class StorageService:
    """Local file storage for claim photos and documents."""

    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}

    def __init__(self):
        self.base_path = settings.upload_path
        self.max_size = settings.max_upload_bytes

    async def save_claim_photos(
        self,
        claim_id: str,
        photos: List[UploadFile],
    ) -> List[str]:
        """
        Save uploaded photos for a claim.

        Args:
            claim_id: Claim identifier (CLM-XXXXXXXX)
            photos: List of uploaded files from FastAPI

        Returns:
            List of saved file paths

        Raises:
            ValueError: If file validation fails
        """
        claim_dir = self.base_path / "claims" / claim_id
        claim_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []

        for i, photo in enumerate(photos):
            # Validate extension
            ext = Path(photo.filename or '').suffix.lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise ValueError(
                    f"Invalid file type '{ext}'. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}"
                )

            # Validate size
            content = await photo.read()
            if len(content) > self.max_size:
                raise ValueError(
                    f"File too large ({len(content) / 1024 / 1024:.1f}MB). "
                    f"Max: {settings.MAX_UPLOAD_SIZE_MB}MB"
                )

            # Generate unique filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            file_hash = hashlib.md5(content[:1024]).hexdigest()[:8]
            filename = f"{claim_id}_{i}_{timestamp}_{file_hash}{ext}"
            file_path = claim_dir / filename

            # Save file
            async with aiofiles.open(str(file_path), 'wb') as f:
                await f.write(content)

            saved_paths.append(str(file_path))
            logger.info(f"Saved photo: {file_path} ({len(content) / 1024:.1f}KB)")

            # Reset file position for potential re-read
            await photo.seek(0)

        return saved_paths

    async def delete_claim_photos(self, claim_id: str) -> int:
        """Delete all photos for a claim. Returns count of deleted files."""
        claim_dir = self.base_path / "claims" / claim_id
        if not claim_dir.exists():
            return 0

        count = 0
        for file_path in claim_dir.iterdir():
            if file_path.is_file():
                file_path.unlink()
                count += 1

        try:
            claim_dir.rmdir()
        except OSError:
            pass

        logger.info(f"Deleted {count} photos for claim {claim_id}")
        return count

    def get_claim_photo_paths(self, claim_id: str) -> List[str]:
        """Get all photo paths for a claim."""
        claim_dir = self.base_path / "claims" / claim_id
        if not claim_dir.exists():
            return []
        return sorted([str(p) for p in claim_dir.iterdir() if p.is_file()])


# Singleton
storage_service = StorageService()
