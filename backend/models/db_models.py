# backend/models/db_models.py — SQLAlchemy ORM models with PostGIS geometry
"""
Database models for BhumiRaksha.
Uses PostGIS for village polygon boundaries and claim GPS coordinates.
"""

import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, Date,
    ForeignKey, Enum as SQLEnum, JSON, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from database import Base
import enum


# ── Enums ─────────────────────────────────────────────────────────────

class ClaimStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AUTO_APPROVED = "AUTO_APPROVED"
    OFFICER_REVIEW = "OFFICER_REVIEW"
    FIELD_VERIFICATION = "FIELD_VERIFICATION"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FRAUD_FLAGGED = "FRAUD_FLAGGED"
    PAYMENT_QUEUED = "PAYMENT_QUEUED"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"


class DamageTypeEnum(str, enum.Enum):
    CROP = "crop"
    HOUSE = "house"
    BOTH = "both"
    LIVESTOCK = "livestock"
    INFRASTRUCTURE = "infrastructure"


class CropTypeEnum(str, enum.Enum):
    PADDY_RAINFED = "paddy_rainfed"
    PADDY_IRRIGATED = "paddy_irrigated"
    WHEAT = "wheat"
    JUTE = "jute"
    SUGARCANE = "sugarcane"
    VEGETABLES = "vegetables"
    PERENNIAL_CROPS = "perennial_crops"


class HouseDamageEnum(str, enum.Enum):
    PUCCA_FULL = "pucca_full"
    PUCCA_PARTIAL = "pucca_partial"
    KUTCHA_FULL = "kutcha_full"
    KUTCHA_PARTIAL = "kutcha_partial"


class AuditActionEnum(str, enum.Enum):
    CLAIM_SUBMITTED = "CLAIM_SUBMITTED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    FRAUD_DETECTED = "FRAUD_DETECTED"
    OFFICER_APPROVED = "OFFICER_APPROVED"
    OFFICER_REJECTED = "OFFICER_REJECTED"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    SMS_SENT = "SMS_SENT"


# ── Models ────────────────────────────────────────────────────────────

class Village(Base):
    """Village boundary with PostGIS polygon from Census shapefiles."""
    __tablename__ = "villages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    district = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False, index=True)
    block = Column(String(100))
    revenue_circle = Column(String(100))
    # PostGIS polygon boundary
    boundary = Column(Geometry("POLYGON", srid=4326), nullable=False)
    area_ha = Column(Float)  # Total area in hectares
    centroid_lat = Column(Float)
    centroid_lon = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    gaon_buras = relationship("GaonBura", back_populates="village")
    claims = relationship("Claim", back_populates="village")

    __table_args__ = (
        Index("ix_village_boundary", "boundary", postgresql_using="gist"),
    )


class GaonBura(Base):
    """Village head (Gaon Bura) — the primary reporter."""
    __tablename__ = "gaon_buras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aadhaar_hash = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(15), nullable=False)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    is_suspended = Column(Boolean, default=False)  # Suspended for fraud
    fraud_flags_count = Column(Integer, default=0)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    village = relationship("Village", back_populates="gaon_buras")
    claims = relationship("Claim", back_populates="gaon_bura")


class FloodEvent(Base):
    """A recorded flood event — used to validate claim timing."""
    __tablename__ = "flood_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_date = Column(Date, nullable=False, index=True)
    state = Column(String(100), nullable=False, index=True)
    districts_affected = Column(JSONB)  # list of district names
    severity = Column(String(20))  # LOW / MEDIUM / HIGH / SEVERE
    # Satellite-confirmed flood extent (GeoJSON)
    flood_extent = Column(Geometry("MULTIPOLYGON", srid=4326))
    source = Column(String(50))  # SAR / NEWS / CWC / MANUAL
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claims = relationship("Claim", back_populates="flood_event")


class Claim(Base):
    """Individual damage claim submitted by a Gaon Bura."""
    __tablename__ = "claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(String(20), unique=True, nullable=False, index=True)  # CLM-XXXXXXXX
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=False)
    gaon_bura_id = Column(UUID(as_uuid=True), ForeignKey("gaon_buras.id"), nullable=False)
    flood_event_id = Column(UUID(as_uuid=True), ForeignKey("flood_events.id"), nullable=True)

    # Damage details
    damage_type = Column(SQLEnum(DamageTypeEnum), nullable=False)
    crop_type = Column(SQLEnum(CropTypeEnum), nullable=True)
    house_damage_type = Column(SQLEnum(HouseDamageEnum), nullable=True)
    claimed_area_ha = Column(Float, nullable=False)
    damage_percentage = Column(Float)  # 0.0 - 1.0

    # Location
    submitted_lat = Column(Float, nullable=False)
    submitted_lon = Column(Float, nullable=False)
    submitted_point = Column(Geometry("POINT", srid=4326))
    event_date = Column(Date, nullable=False)

    # Verification results
    status = Column(SQLEnum(ClaimStatusEnum), default=ClaimStatusEnum.PENDING, index=True)
    ground_score = Column(Integer)  # 0–50
    satellite_score = Column(Integer)  # 0–50
    total_score = Column(Integer)  # 0–100
    fraud_flags = Column(JSONB, default=list)

    # Compensation
    estimated_compensation = Column(Float, default=0)
    approved_compensation = Column(Float)
    compensation_breakdown = Column(JSONB)

    # Satellite analysis
    flooded_area_ha = Column(Float)
    flood_percentage = Column(Float)
    ndvi_loss = Column(Float)
    satellite_confidence = Column(String(10))  # HIGH / MEDIUM / LOW

    # Payment
    payment_status = Column(String(30))
    payment_reference = Column(String(50))
    payment_date = Column(DateTime)

    # SMS
    sms_message = Column(Text)

    # Timestamps
    submitted_at = Column(DateTime, default=datetime.utcnow, index=True)
    verified_at = Column(DateTime)
    approved_at = Column(DateTime)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("officers.id"), nullable=True)

    # Relationships
    village = relationship("Village", back_populates="claims")
    gaon_bura = relationship("GaonBura", back_populates="claims")
    flood_event = relationship("FloodEvent", back_populates="claims")
    photos = relationship("ClaimPhoto", back_populates="claim", cascade="all, delete-orphan")
    verification = relationship("VerificationResult", back_populates="claim", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="claim")
    approver = relationship("Officer", back_populates="approved_claims")

    __table_args__ = (
        Index("ix_claim_submitted_point", "submitted_point", postgresql_using="gist"),
        Index("ix_claim_status_district", "status", "village_id"),
    )


class ClaimPhoto(Base):
    """Photos uploaded with a claim — geo-tagged and hash-indexed."""
    __tablename__ = "claim_photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255))

    # EXIF data
    exif_lat = Column(Float)
    exif_lon = Column(Float)
    exif_datetime = Column(DateTime)
    exif_valid = Column(Boolean)

    # Analysis results
    perceptual_hash = Column(String(64), index=True)
    is_duplicate = Column(Boolean, default=False)
    flood_detected = Column(Boolean)
    damage_class = Column(String(30))
    confidence = Column(Float)
    ground_score = Column(Integer)

    # Flags
    flags = Column(JSONB, default=list)

    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="photos")


class VerificationResult(Base):
    """Complete verification result for a claim."""
    __tablename__ = "verification_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), unique=True, nullable=False)

    # Ground analysis (best of all photos)
    ground_score = Column(Integer, nullable=False)
    ground_flood_detected = Column(Boolean)
    ground_damage_class = Column(String(30))
    ground_confidence = Column(Float)

    # Satellite analysis
    satellite_score = Column(Integer, nullable=False)
    flooded_area_ha = Column(Float)
    flood_percentage = Column(Float)
    ndvi_loss = Column(Float)
    satellite_confidence = Column(String(10))

    # Combined
    total_score = Column(Integer, nullable=False)
    status = Column(SQLEnum(ClaimStatusEnum), nullable=False)
    fraud_flags = Column(JSONB, default=list)

    # Compensation
    estimated_compensation = Column(Float)
    compensation_breakdown = Column(JSONB)

    processed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    claim = relationship("Claim", back_populates="verification")


class Officer(Base):
    """District officer / Tehsildar who reviews claims."""
    __tablename__ = "officers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    designation = Column(String(100))  # Tehsildar, DM, SDO, etc.
    district = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False)
    phone = Column(String(15))
    email = Column(String(200))
    password_hash = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    approved_claims = relationship("Claim", back_populates="approver")


class AuditLog(Base):
    """Immutable audit trail for every action on a claim."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False, index=True)
    action = Column(SQLEnum(AuditActionEnum), nullable=False)
    actor_type = Column(String(20))  # SYSTEM / GAON_BURA / OFFICER
    actor_id = Column(String(100))
    details = Column(JSONB)
    # Blockchain hash (for Hyperledger integration)
    ledger_hash = Column(String(128))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    claim = relationship("Claim", back_populates="audit_logs")
