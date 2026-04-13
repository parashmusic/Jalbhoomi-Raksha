# backend/utils/image_utils.py — Image processing helpers
"""Image utility functions for preprocessing and metadata extraction."""

from typing import Optional, Tuple
from pathlib import Path
from loguru import logger

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import exifread
    EXIF_AVAILABLE = True
except ImportError:
    EXIF_AVAILABLE = False


def resize_image(
    image_path: str,
    max_size: int = 640,
    output_path: Optional[str] = None,
) -> str:
    """
    Resize image to max dimension while preserving aspect ratio.
    YOLOv8 expects 640px input.

    Args:
        image_path: Path to input image
        max_size: Maximum dimension (width or height)
        output_path: Optional output path (defaults to overwriting input)

    Returns:
        Path to resized image
    """
    if not PIL_AVAILABLE:
        logger.warning("Pillow not available — skipping resize")
        return image_path

    output = output_path or image_path

    try:
        img = Image.open(image_path)
        w, h = img.size

        if max(w, h) <= max_size:
            return image_path

        if w > h:
            new_w = max_size
            new_h = int(h * max_size / w)
        else:
            new_h = max_size
            new_w = int(w * max_size / h)

        img_resized = img.resize((new_w, new_h), Image.LANCZOS)
        img_resized.save(output, quality=85)
        logger.debug(f"Resized {w}x{h} → {new_w}x{new_h}: {output}")
        return output

    except Exception as e:
        logger.error(f"Image resize failed: {e}")
        return image_path


def extract_gps_from_exif(
    image_path: str,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract GPS coordinates from image EXIF data.

    Returns:
        Tuple of (latitude, longitude) in decimal degrees, or (None, None)
    """
    if not EXIF_AVAILABLE:
        return None, None

    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, stop_tag='GPS')

        lat = _dms_to_dd(
            tags.get('GPS GPSLatitude'),
            tags.get('GPS GPSLatitudeRef')
        )
        lon = _dms_to_dd(
            tags.get('GPS GPSLongitude'),
            tags.get('GPS GPSLongitudeRef')
        )

        return lat, lon

    except Exception as e:
        logger.error(f"EXIF GPS extraction failed: {e}")
        return None, None


def _dms_to_dd(dms_tag, ref_tag=None) -> Optional[float]:
    """Convert EXIF DMS to decimal degrees."""
    if dms_tag is None:
        return None

    try:
        values = dms_tag.values
        d = float(values[0].num) / float(values[0].den)
        m = float(values[1].num) / float(values[1].den)
        s = float(values[2].num) / float(values[2].den)
        dd = d + m / 60 + s / 3600

        if ref_tag and str(ref_tag) in ['S', 'W']:
            dd *= -1
        return dd
    except (AttributeError, IndexError, ZeroDivisionError):
        return None
