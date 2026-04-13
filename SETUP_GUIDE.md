# BhumiRaksha — Setup & Next Steps Guide

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Backend (FastAPI) | **Running** | `http://localhost:8000` |
| API Docs (Swagger) | **Running** | `http://localhost:8000/docs` |
| Health Check | **Passing** | Returns `{"status":"healthy"}` |
| Rates API | **Working** | All NDRF rates served |
| YOLOv8 Model | **Mock Mode** | Works without model weights |
| SAR Processor | **Mock Mode** | Works without GEE credentials |
| PostgreSQL | **Not running** | Optional — server works without it |
| Redis | **Not running** | Optional — uses in-memory fallback |

> [!TIP]
> The server is already working in **development/mock mode** — all AI features return simulated but realistic results. You can test every endpoint without any external services.

---

## What You Can Do RIGHT NOW

### 1. Open the API Docs
```
http://localhost:8000/docs
```
Interactive Swagger UI — you can test all endpoints directly from your browser.

### 2. Test Endpoints (from browser or Postman)

| URL | What it does |
|-----|-------------|
| `http://localhost:8000/` | Root — app info |
| `http://localhost:8000/api/v1/health` | Health check |
| `http://localhost:8000/api/v1/rates` | NDRF compensation rate tables |
| `http://localhost:8000/api/v1/info` | System capabilities |
| `http://localhost:8000/api/v1/officer/stats` | District stats (needs login first) |

### 3. Test the Claim Submission (via Swagger or curl)
Go to `http://localhost:8000/docs`, find **POST /api/v1/claims/submit**, click "Try it out", and upload 3+ images with the form fields.

---

## Optional Setup Steps (When You're Ready)

### Step A: Install Docker Desktop & Start Database

If you want **persistent data storage** with PostgreSQL + PostGIS:

```powershell
# 1. Install Docker Desktop from https://docker.com/products/docker-desktop
# 2. After install, run:
cd "d:\Flood Detection"
docker-compose up -d db redis
```

This starts:
- **PostgreSQL 16 + PostGIS** on port `5432`
- **Redis 7** on port `6379`

The server will auto-connect on next restart.

### Step B: Install ML Dependencies (for real AI inference)

```powershell
# Activate venv
d:\Flood` Detection\backend\venv\Scripts\activate

# Install PyTorch (CPU version — ~2GB download)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install YOLOv8
pip install ultralytics

# Install numpy + opencv
pip install numpy opencv-python-headless
```

Then place your trained model at:
```
d:\Flood Detection\models\flood_yolov8m.pt
```

### Step C: Setup Google Earth Engine (for real satellite analysis)

```powershell
# Install GEE
pip install earthengine-api

# Authenticate (opens browser)
earthengine authenticate
```

Or use service account:
1. Create GEE project at https://code.earthengine.google.com
2. Generate service account key JSON
3. Set in `.env`:
   ```
   GEE_SERVICE_ACCOUNT=your-account@project.iam.gserviceaccount.com
   GEE_KEY_FILE=./keys/gee-service-key.json
   ```

### Step D: Setup Git

```powershell
cd "d:\Flood Detection"
git init
git add .
git commit -m "Initial commit: BhumiRaksha flood detection system"

# If you have a GitHub repo:
git remote add origin https://github.com/YOUR_USERNAME/bhumiraksha.git
git push -u origin main
```

---

## Server Commands Reference

```powershell
# Start the server (from backend dir)
cd "d:\Flood Detection\backend"
.\venv\Scripts\activate
uvicorn main:app --reload --port 8000

# Stop the server
Ctrl+C

# Start database (if Docker is installed)
cd "d:\Flood Detection"
docker-compose up -d db redis

# Stop database
docker-compose down
```

---

## Project File Map

```
d:\Flood Detection\
│
├── backend\main.py              ← START HERE (entry point)
├── backend\config.py             ← All settings (.env)
├── backend\core\                 ← AI/ML logic (the brain)
│   ├── flood_detector.py         ← YOLOv8 photo analysis
│   ├── sar_processor.py          ← Satellite flood mapping
│   ├── verification_engine.py    ← Score fusion (50+50=100)
│   ├── compensation.py           ← NDRF rate calculator
│   └── fraud_detector.py         ← Anti-fraud checks
├── backend\api\routes\           ← API endpoints
│   ├── claims.py                 ← Submit/check claims
│   └── officer.py                ← Officer dashboard
├── backend\services\             ← External integrations
│   ├── sms_service.py            ← SMS notifications
│   └── pfms_service.py           ← Govt payment system
└── backend\.env                  ← Your config (edit this)
```

---

## What's Coming Next

When you're ready, I'll build:
1. **Dashboard (Next.js)** — Officer web portal with map visualization
2. **Database migrations** — Alembic for schema management
3. **Train/download ML models** — YOLOv8 + SegFormer
