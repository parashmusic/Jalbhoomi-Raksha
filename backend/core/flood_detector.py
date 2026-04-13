# backend/core/flood_detector.py — Ground photo flood classification using YOLOv8
"""
Analyzes phone photos uploaded by Gaon Bura to detect flood damage.
Uses YOLOv8 for classification, EXIF metadata for GPS/timestamp validation,
and perceptual hashing for duplicate detection.

Outputs a Ground Score (0–50) that forms half of the dual verification.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

import hashlib

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("ultralytics not installed — flood_detector will use mock mode")

try:
    from PIL import Image
    import exifread
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from shapely.geometry import Point
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False


@dataclass
class GroundAnalysisResult:
    """Result of analyzing a single ground-level photo."""
    flood_detected: bool
    confidence: float         # 0.0 – 1.0
    ground_score: int         # 0 – 50
    damage_class: str         # flood / partial_flood / crop_damage / house_damage / no_damage
    gps_valid: bool
    timestamp_valid: bool
    is_duplicate: bool
    flags: List[str] = field(default_factory=list)


class FloodGroundDetector:
    """
    YOLOv8-based flood detection from Gaon Bura phone photos.

    Pipeline:
      1. Perceptual hash → duplicate detection
      2. EXIF metadata → GPS + timestamp validation
      3. YOLOv8 inference → flood/damage classification
      4. Score computation with penalty deductions
    """

    CLASSES = {
        0: 'flood',
        1: 'partial_flood',
        2: 'crop_damage',
        3: 'house_damage',
        4: 'no_damage',
    }

    SCORE_MAP = {
        'flood': 45,
        'partial_flood': 30,
        'crop_damage': 25,
        'house_damage': 20,
        'no_damage': 5,
    }

    def __init__(self, model_path: str, image_hash_db: Optional[Set[str]] = None):
        """
        Args:
            model_path: Path to trained YOLOv8 model weights (.pt file)
            image_hash_db: Set of previously seen perceptual hashes.
                           In production, this would be backed by Redis.
        """
        self.model = None
        self.model_path = model_path

        if YOLO_AVAILABLE and Path(model_path).exists():
            try:
                self.model = YOLO(model_path)
                logger.info(f"YOLOv8 model loaded from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load YOLO model: {e}. Using mock mode.")

        # In production, replace with Redis set
        self.hash_db = image_hash_db if image_hash_db is not None else set()

    def analyze(
        self,
        image_path: str,
        submitted_lat: float,
        submitted_lon: float,
        event_date: datetime,
        village_polygon=None,
    ) -> GroundAnalysisResult:
        """
        Analyze a single ground-level photo for flood damage.

        Args:
            image_path: Path to the uploaded photo
            submitted_lat: GPS latitude submitted by the app
            submitted_lon: GPS longitude submitted by the app
            event_date: Date of the reported flood event
            village_polygon: Shapely polygon of the village boundary

        Returns:
            GroundAnalysisResult with score, classification, and flags
        """
        flags = []
        logger.info(f"Analyzing ground photo: {image_path}")

        # ── 1. Duplicate detection via perceptual hash ─────────────
        is_dup = False
        if PIL_AVAILABLE and Path(image_path).exists():
            try:
                img = Image.open(image_path)
                img_hash = self._phash(img)
                is_dup = img_hash in self.hash_db
                if is_dup:
                    flags.append('DUPLICATE_IMAGE')
                    logger.warning(f"Duplicate image detected: {img_hash}")
                # Store hash to prevent reuse
                self.hash_db.add(img_hash)
            except Exception as e:
                logger.error(f"Image hash failed: {e}")
                flags.append('HASH_ERROR')
        else:
            flags.append('IMAGE_NOT_FOUND')

        # ── 2. EXIF metadata validation ────────────────────────────
        gps_ok, ts_ok = self._validate_exif(
            image_path, submitted_lat, submitted_lon,
            event_date, village_polygon, flags
        )

        # ── 3. YOLOv8 inference ────────────────────────────────────
        if self.model is not None:
            try:
                results = self.model.predict(image_path, conf=0.4, verbose=False)
                top_class, confidence = self._parse_preds(results[0])
            except Exception as e:
                logger.error(f"YOLO inference failed: {e}")
                top_class, confidence = 'no_damage', 0.0
                flags.append('INFERENCE_ERROR')
        else:
            # Mock mode — simulate inference for development
            top_class, confidence = self._mock_inference(image_path)
            flags.append('MOCK_INFERENCE')

        # ── 4. Score computation ───────────────────────────────────
        base_score = self.SCORE_MAP.get(top_class, 0)
        score = base_score

        if not gps_ok:
            score -= 15
            if 'GPS_MISMATCH' not in flags:
                flags.append('GPS_MISMATCH')

        if not ts_ok:
            score -= 10
            if 'TIMESTAMP_STALE' not in flags:
                flags.append('TIMESTAMP_STALE')

        if is_dup:
            score = 0  # Full penalty for duplicates

        return GroundAnalysisResult(
            flood_detected=(top_class in ['flood', 'partial_flood']),
            confidence=confidence,
            ground_score=max(0, min(50, score)),
            damage_class=top_class,
            gps_valid=gps_ok,
            timestamp_valid=ts_ok,
            is_duplicate=is_dup,
            flags=flags,
        )

    def _validate_exif(
        self, path: str, lat: float, lon: float,
        event_dt: datetime, polygon, flags: List[str]
    ) -> tuple:
        """Validate EXIF GPS and timestamp against submitted data."""
        gps_ok = False
        ts_ok = False

        if not Path(path).exists():
            return False, False

        try:
            with open(path, 'rb') as f:
                tags = exifread.process_file(f, stop_tag='GPS')

            # GPS coords from EXIF must be within village polygon (±500m)
            exif_lat = self._dms_to_dd(tags.get('GPS GPSLatitude'),
                                        tags.get('GPS GPSLatitudeRef'))
            exif_lon = self._dms_to_dd(tags.get('GPS GPSLongitude'),
                                        tags.get('GPS GPSLongitudeRef'))

            if exif_lat is not None and exif_lon is not None:
                if polygon is not None and SHAPELY_AVAILABLE:
                    gps_ok = polygon.buffer(0.005).contains(  # ~500m tolerance
                        Point(exif_lon, exif_lat)
                    )
                else:
                    # Fallback: check distance from submitted coords
                    dist = ((exif_lat - lat) ** 2 + (exif_lon - lon) ** 2) ** 0.5
                    gps_ok = dist < 0.01  # ~1km tolerance
            else:
                # No EXIF GPS — check submitted coords against polygon
                if polygon is not None and SHAPELY_AVAILABLE:
                    gps_ok = polygon.buffer(0.005).contains(Point(lon, lat))
                else:
                    gps_ok = True  # Accept if no polygon available
                flags.append('NO_EXIF_GPS')

            # Photo must be taken within 72h of event
            exif_dt_str = str(tags.get('EXIF DateTimeOriginal', ''))
            if exif_dt_str:
                try:
                    exif_dt = datetime.strptime(exif_dt_str, '%Y:%m:%d %H:%M:%S')
                    ts_ok = abs((exif_dt - event_dt).total_seconds()) < 72 * 3600
                except (ValueError, TypeError):
                    ts_ok = False
                    flags.append('EXIF_DATE_PARSE_ERROR')
            else:
                ts_ok = False
                flags.append('NO_EXIF_TIMESTAMP')

        except Exception as e:
            logger.error(f"EXIF validation failed: {e}")
            flags.append('EXIF_READ_ERROR')

        return gps_ok, ts_ok

    def _parse_preds(self, result) -> tuple:
        """Parse YOLOv8 predictions to get top class and confidence."""
        if hasattr(result, 'probs') and result.probs is not None:
            # Classification result
            probs = result.probs
            top_idx = probs.top1
            top_conf = float(probs.top1conf)
            top_class = self.CLASSES.get(top_idx, 'no_damage')
            return top_class, top_conf
        elif hasattr(result, 'boxes') and len(result.boxes) > 0:
            # Detection result — get highest confidence box
            boxes = result.boxes
            best_idx = boxes.conf.argmax().item()
            cls_id = int(boxes.cls[best_idx].item())
            conf = float(boxes.conf[best_idx].item())
            top_class = self.CLASSES.get(cls_id, 'no_damage')
            return top_class, conf
        else:
            return 'no_damage', 0.0

    def _mock_inference(self, image_path: str) -> tuple:
        """Mock inference for development without ML model."""
        # Deterministic mock based on filename hash
        name_hash = hashlib.md5(image_path.encode()).hexdigest()
        hash_val = int(name_hash[:4], 16) % 100

        if hash_val < 40:
            return 'flood', 0.85
        elif hash_val < 60:
            return 'partial_flood', 0.72
        elif hash_val < 75:
            return 'crop_damage', 0.68
        elif hash_val < 85:
            return 'house_damage', 0.65
        else:
            return 'no_damage', 0.90

    def _phash(self, img) -> str:
        """Compute perceptual hash for duplicate detection."""
        img_small = img.convert('L').resize((16, 16))
        pixels = list(img_small.getdata())
        avg = sum(pixels) / len(pixels)
        bits = ''.join('1' if p > avg else '0' for p in pixels)
        return hex(int(bits, 2))

    def _dms_to_dd(self, dms_tag, ref_tag=None) -> Optional[float]:
        """Convert EXIF DMS (degrees/minutes/seconds) to decimal degrees."""
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
