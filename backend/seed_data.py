# backend/seed_data.py — Initial data for testing
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from database import engine, async_session, init_db
from models.db_models import Village, Officer
from api.dependencies import hash_password
from shapely.geometry import Polygon
import uuid

async def seed():
    print("🌱 Seeding initial data...")
    async with async_session() as db:
        # 1. Create a Test Village (Kamrup, Assam)
        test_village = Village(
            id=uuid.uuid4(),
            name="Nambari Gaon",
            village_code="VIL-ASSAM-001",
            district="Kamrup",
            state="Assam",
            # A simple square polygon around a test coordinate (Long Lat)
            boundary="SRID=4326;POLYGON((91.70 26.10, 91.80 26.10, 91.80 26.20, 91.70 26.20, 91.70 26.10))",
            area_ha=150.5
        )
        
        # 2. Create a Test Officer
        test_officer = Officer(
            id=uuid.uuid4(),
            employee_id="OFF-001",
            name="Rajesh Kumar",
            district="Kamrup",
            state="Assam",
            designation="District Disaster Manager",
            password_hash=hash_password("admin123"),
            is_active=True
        )
        
        db.add(test_village)
        db.add(test_officer)
        
        try:
            await db.commit()
            print("✅ Successfully seeded 1 Village and 1 Officer.")
        except Exception as e:
            print(f"❌ Error seeding: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(seed())
